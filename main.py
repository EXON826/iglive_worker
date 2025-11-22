# worker/main.py

import os
import json
import logging
import asyncio
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from handlers import (
    start_handler,
    my_account_handler,
    check_live_handler,
    join_request_handler,
    broadcast_message_handler,
    handle_broadcast_command,
    notify_live_handler,
    init_handler,
    activate_handler,
    back_handler,
    help_handler,
    referrals_handler,
    settings_handler,
    set_initial_language_handler,
    change_language_handler,
    toggle_notifications_handler,
    clear_notifications_handler,
    check_and_trigger_auto_broadcast,
)
from rate_limiter import rate_limiter
from payment_handlers import (
    buy_handler,
    payment_handler,
    pre_checkout_handler,
    successful_payment_handler,
)

# --- Enhanced Logging Setup ---
from logging_config import setup_production_logging
logger = setup_production_logging()

POLLING_INTERVAL = 2 # seconds

async def process_job(job, session_factory):
    """
    Processes a job from the queue by routing it to the appropriate handler.
    """
    job_id = job['job_id']
    job_type = job['job_type']
    payload_data = job.get('payload', '{}')

    # Safely parse the JSON payload
    try:
        if isinstance(payload_data, str):
            payload = json.loads(payload_data)
        elif isinstance(payload_data, dict):
            payload = payload_data
        else:
            logger.error(f"Payload for job_id: {job_id} is not a dict or a valid JSON string.")
            return False
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"Invalid JSON payload for job_id: {job_id}. Payload: {payload_data}, Error: {e}")
        return False

    start_time = time.time()
    logger.info(f"Processing job_id: {job_id} of type: {job_type}")
    session = session_factory()

    try:
        if job_type == 'process_telegram_update':
            if 'message' in payload:
                # Check for successful payment first
                if 'successful_payment' in payload['message']:
                    await successful_payment_handler(session, payload)
                else:
                    text = payload['message'].get('text', '').strip()
                    if text.startswith('/start'):
                        await start_handler(session, payload)
                    elif text.startswith('/init'):
                        await init_handler(session, payload)
                    elif text.startswith('/activate'):
                        await activate_handler(session, payload)
                    elif text.startswith('/broadcast'):
                        await handle_broadcast_command(session, payload)
            elif 'callback_query' in payload:
                # Rate limiting for button clicks
                sender_id = payload['callback_query'].get('from', {}).get('id')
                if sender_id and not rate_limiter.is_allowed(sender_id, 'button_click'):
                    logger.warning(f"Button click rate limit exceeded for user {sender_id}")
                    return True  # Consider as processed to avoid retries
                
                callback_data = payload['callback_query'].get('data')
                if callback_data == 'my_account':
                    await my_account_handler(session, payload)
                elif callback_data == 'check_live' or callback_data.startswith('check_live:'):
                    await check_live_handler(session, payload)
                elif callback_data == 'back':
                    await back_handler(session, payload)
                elif callback_data == 'help':
                    await help_handler(session, payload)
                elif callback_data == 'referrals':
                    await referrals_handler(session, payload)
                elif callback_data == 'settings':
                    await settings_handler(session, payload)
                elif callback_data == 'buy':
                    await buy_handler(session, payload)
                elif callback_data.startswith('pay:'):
                    await payment_handler(session, payload)
                elif callback_data.startswith('setlang:'):
                    await set_initial_language_handler(session, payload)
                elif callback_data.startswith('lang:'):
                    await change_language_handler(session, payload)
                elif callback_data == 'toggle_notifications':
                    await toggle_notifications_handler(session, payload)
                elif callback_data == 'clear_notifications':
                    await clear_notifications_handler(session, payload)
                else:
                    logger.info(f"No handler for callback_data: '{callback_data}'")
            elif 'pre_checkout_query' in payload:
                logger.info(f"PRE_CHECKOUT_QUERY detected in payload: {payload.get('pre_checkout_query', {}).get('id')}")
                await pre_checkout_handler(session, payload)
            elif 'chat_join_request' in payload:
                await join_request_handler(session, payload)
            else:
                logger.info(f"No handler for this update type.")
        
        elif job_type == 'broadcast_message':
            await broadcast_message_handler(session, payload)

        elif job_type == 'notify_live':
            await notify_live_handler(session, payload)

        else:
            logger.warning(f"Unknown job_type: {job_type}")

        return True
    except Exception as e:
        logger.error(f"A handler raised an exception for job {job_id}: {e}", exc_info=True)
        return False # Explicitly return False on error
    finally:
        session.close()

async def worker_main_loop(session_factory, run_once=False):
    """
    The main loop for the worker.
    - Fetches a pending job from the database.
    - Marks it as 'processing'.
    - Calls process_job to handle it.
    - Updates the job status based on the result.
    """
    run_once_retries = 0
    last_auto_broadcast_check = 0
    AUTO_BROADCAST_CHECK_INTERVAL = 300  # 5 minutes

    while True:
        job_to_process = None
        session = session_factory()
        try:
            # --- 0. Periodic Auto-Broadcast Check ---
            current_time = time.time()
            if current_time - last_auto_broadcast_check > AUTO_BROADCAST_CHECK_INTERVAL:
                await check_and_trigger_auto_broadcast(session)
                last_auto_broadcast_check = current_time

            # --- 1. Fetch and Lock a Job ---
            select_query = text("""
                SELECT * FROM jobs
                WHERE status = 'pending' AND job_type != 'send_to_groups'
                ORDER BY created_at
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """)
            result = session.execute(select_query).fetchone()

            if result:
                job_to_process = dict(result._mapping)
                update_query = text("""
                    UPDATE jobs
                    SET status = 'processing', updated_at = :now
                    WHERE job_id = :job_id
                """)
                session.execute(update_query, {'now': datetime.now(timezone.utc), 'job_id': job_to_process['job_id']})
                session.commit()
                logger.info(f"Locked and picked up job_id: {job_to_process['job_id']}")

            # --- 2. Process the Job ---
            if job_to_process:
                job_start_time = time.time()
                success = await process_job(job_to_process, session_factory)
                
                # --- 3. Update Job Status ---
                retries = job_to_process.get('retries', 0)
                if success:
                    final_status = 'completed'
                else:
                    if retries < 3:
                        final_status = 'pending' # Put it back in the queue for another try
                    else:
                        final_status = 'failed'

                update_query = text("""
                    UPDATE jobs
                    SET status = :status, retries = :retries, updated_at = :now
                    WHERE job_id = :job_id
                """)
                session.execute(update_query, {
                    'status': final_status,
                    'retries': retries + 1 if not success else retries,
                    'now': datetime.now(timezone.utc),
                    'job_id': job_to_process['job_id']
                })
                session.commit()
                
                # Log performance metrics
                processing_time = time.time() - job_start_time
                logger.info(f"Job {job_to_process['job_id']} finished with status: {final_status} in {processing_time:.2f}s")
                
                # Log slow jobs
                if processing_time > 5.0:
                    logger.warning(f"Slow job detected: {job_to_process['job_id']} ({job_to_process['job_type']}) took {processing_time:.2f}s")
                
                if run_once:
                    logger.info("run_once is True, exiting after processing one job.")
                    break
            else:
                if run_once:
                    if run_once_retries >= 2: # Try up to 3 times (0, 1, 2)
                        logger.info("run_once is True, exiting worker loop after multiple attempts.")
                        break
                    run_once_retries += 1
                    logger.info(f"run_once mode: No job found, retrying... (Attempt {run_once_retries})")
                    await asyncio.sleep(1) # Wait a bit for the transaction to commit
                    continue

                await asyncio.sleep(POLLING_INTERVAL)

        except Exception as e:
            logger.error(f"Error in worker main loop: {e}", exc_info=True)
            if session.is_active:
                session.rollback()
            await asyncio.sleep(POLLING_INTERVAL * 2)
        finally:
            session.close()


def main(run_once=False, engine=None):
    # If no engine is passed, create one (for standalone execution)
    if engine is None:
        # Correctly load the .env file from the parent directory
        dotenv_path = os.path.join(os.path.dirname(__file__), '../.env')
        load_dotenv(dotenv_path=dotenv_path)

        DATABASE_URL = os.environ.get('DATABASE_URL')
        if not DATABASE_URL:
            raise ValueError("DATABASE_URL not found in environment.")

        try:
            engine = create_engine(DATABASE_URL)
            logger.info("Database engine created successfully.")
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}", exc_info=True)
            exit(1)
            
    # Create a session factory from the (potentially shared) engine
    SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("Session factory created.")

    logger.info("Starting worker process...")
    
    # Instagram checker runs LOCALLY (not on Railway)
    # Local script updates database, Railway worker just reads it
    logger.info("Instagram checker: Running on local machine (not on Railway)")
    logger.info("Make sure to run local_instagram_checker.py on your PC")
    
    # Run worker (handles Telegram bot only)
    try:
        asyncio.run(worker_main_loop(SessionFactory, run_once=run_once))
    except KeyboardInterrupt:
        logger.info("Worker process stopped by user.")

if __name__ == '__main__':
    main()
