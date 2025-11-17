# Smart Notifications System

## Overview
The smart notifications system provides contextual, behavior-based notifications to improve user engagement and conversions.

## Features Implemented

### 1. Contextual Micro-Copy & Tips ⭐

#### Low Points Alert
- **Trigger:** When user has only 1 point left
- **Message:** Warning with quick actions (refer friend or upgrade)
- **Goal:** Prevent frustration, encourage action before running out

#### Referral Progress Tips
- **Trigger:** Daily reset for users with 10-29 referrals
- **Message:** Motivational message showing progress to free premium
- **Goal:** Keep users engaged with referral program

#### First-Time User Tips
- **Trigger:** After first live check
- **Message:** Welcome message with key features
- **Goal:** Educate new users, improve retention

#### Frequent User Tips
- **Trigger:** After 5+ checks in one day
- **Message:** Suggest premium for power users
- **Goal:** Convert high-engagement users

### 2. Smart Notifications 🔔

#### Point Reset Reminder
- **Schedule:** Daily at 23:00 UTC (1 hour before reset)
- **Target:** Users with 0 points, no premium
- **Message:** Reminder that points reset soon
- **Goal:** Bring users back at optimal time

#### Referral Milestones
- **Trigger:** At 5, 10, 20, 25, 30 referrals
- **Message:** Celebration + progress update
- **Goal:** Gamification, motivation to continue

#### Premium Expiry Warning
- **Schedule:** Daily check for subscriptions expiring in 3 days
- **Target:** Premium users near expiry
- **Message:** Renewal reminder with benefits
- **Goal:** Reduce churn, increase renewals

#### Inactive User Re-engagement
- **Trigger:** 7 days of inactivity
- **Message:** "We miss you" with updates
- **Goal:** Win back inactive users

### 3. Better Error Handling ⚠️

#### Database Errors
- **Behavior:** Refund points, show friendly error
- **Actions:** Try again, contact support
- **Fallback:** Multiple retry strategies

#### Message Edit Failures
- **Behavior:** Fallback to new message
- **Fallback:** Plain text if markdown fails
- **Last Resort:** Simple error message with /start

#### Payment Errors
- **Behavior:** Clear error message with troubleshooting
- **Actions:** Check Telegram Stars, retry, support
- **Goal:** Reduce payment abandonment

## Setup Instructions

### 1. Scheduled Jobs (Optional but Recommended)

Add these to your cron or task scheduler:

```bash
# Point reset reminders (daily at 23:00 UTC)
0 23 * * * python -c "from smart_notifications import send_point_reset_reminder; import asyncio; from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; engine = create_engine('YOUR_DB_URL'); Session = sessionmaker(bind=engine); session = Session(); asyncio.run(send_point_reset_reminder(session))"

# Premium expiry warnings (daily at 10:00 UTC)
0 10 * * * python -c "from smart_notifications import send_premium_expiry_warning; import asyncio; from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker; engine = create_engine('YOUR_DB_URL'); Session = sessionmaker(bind=engine); session = Session(); asyncio.run(send_premium_expiry_warning(session))"
```

### 2. Environment Variables

No additional environment variables needed. Uses existing:
- `BOT_TOKEN`
- `DATABASE_URL`

## Usage Examples

### Manual Notification Trigger

```python
from smart_notifications import send_contextual_tip
import asyncio

# Send tip to user
asyncio.run(send_contextual_tip(
    user_id=123456789,
    tip_type='frequent_user',
    checks_today=7
))
```

### Check Milestone Notifications

```python
from smart_notifications import send_referral_milestone_notification
import asyncio

# After a referral
asyncio.run(send_referral_milestone_notification(
    session=session,
    user_id=123456789,
    referral_count=10
))
```

## Notification Types Summary

| Type | Trigger | Frequency | Goal |
|------|---------|-----------|------|
| Low Points Alert | 1 point left | Per check | Prevent churn |
| Referral Progress | Daily reset | Daily | Motivate referrals |
| Point Reset Reminder | 23:00 UTC | Daily | Re-engagement |
| Milestone | Referral count | Per milestone | Gamification |
| Premium Expiry | 3 days before | Once | Reduce churn |
| First Check | First live check | Once | Education |
| Frequent User | 5+ checks/day | Once/day | Conversion |
| Inactive User | 7 days inactive | Once | Win-back |

## Metrics to Track

1. **Engagement Metrics:**
   - Click-through rate on notification CTAs
   - Time to action after notification
   - Return rate after reminders

2. **Conversion Metrics:**
   - Premium upgrades from low-point alerts
   - Referrals from milestone notifications
   - Renewals from expiry warnings

3. **Retention Metrics:**
   - Inactive user return rate
   - Daily active users trend
   - Churn rate reduction

## Best Practices

1. **Don't Over-Notify:** Max 2-3 notifications per day per user
2. **Respect Timezone:** Consider user's local time for reminders
3. **A/B Test Messages:** Test different copy for better results
4. **Monitor Opt-Outs:** Track if users block bot after notifications
5. **Personalize:** Use user's name and relevant data

## Future Enhancements

- [ ] User notification preferences
- [ ] Timezone-aware scheduling
- [ ] A/B testing framework
- [ ] Analytics dashboard
- [ ] Push notification integration
- [ ] Smart send time optimization
- [ ] Notification frequency capping
- [ ] Multi-language support for all notifications

## Troubleshooting

### Notifications Not Sending

1. Check bot token is valid
2. Verify user hasn't blocked bot
3. Check database connection
4. Review logs for errors

### Scheduled Jobs Not Running

1. Verify cron syntax
2. Check Python path
3. Ensure database URL is accessible
4. Test manually first

### High Opt-Out Rate

1. Reduce notification frequency
2. Improve message relevance
3. Add opt-out preferences
4. A/B test message copy

## Support

For issues or questions:
- Check logs in `worker/main.py`
- Review error messages in console
- Contact development team
