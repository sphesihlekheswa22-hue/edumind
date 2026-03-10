# Setting Up PostgreSQL on Render

## Step 1: Create PostgreSQL Database on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **PostgreSQL**
3. Configure:
   - **Name**: edumind-db
   - **Database**: edumind
   - **User**: edumind
   - **Password**: (copy this - you'll need it)
4. Click **Create Database**

## Step 2: Copy the Connection String

After creation, you'll see a "Internal Database URL" like:
```
postgres://edumind:password@host.render.com:5432/edumind
```

## Step 3: Update Render Web Service

1. Go to your **edumind** web service
2. Click **Environment**
3. Add these variables:
   - `DATABASE_URL`: (paste your PostgreSQL connection string)
   - `SECRET_KEY`: (generate a secure random string)
4. Click **Save Changes**

## Step 4: Redeploy

Click **Manual Deploy** → **Deploy latest commit**

The app will automatically:
- Detect PostgreSQL and create tables
- Seed sample data on first run
- Persist data forever (even when service sleeps)
