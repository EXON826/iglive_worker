-- Migration to add Telegram Stars payment support
-- Run this SQL on your database

-- Create star_payments table
CREATE TABLE IF NOT EXISTS star_payments (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES telegram_users(id),
    telegram_payment_charge_id VARCHAR(255) UNIQUE NOT NULL,
    amount INTEGER NOT NULL,
    package_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending' NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    completed_at TIMESTAMP
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_star_payments_user_id ON star_payments(user_id);
CREATE INDEX IF NOT EXISTS idx_star_payments_status ON star_payments(status);

-- Create bots table (if needed)
CREATE TABLE IF NOT EXISTS bots (
    bot_token VARCHAR(255) PRIMARY KEY NOT NULL
);
