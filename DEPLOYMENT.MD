# Run this

## Connect to AWS 
--profile austin


## Start venv
.\venv\Scripts\Activate.ps1


## Create secret if needed
python -c "import secrets; print(secrets.token_urlsafe(32))"
## Set env variables
$env:AWS_PROFILE="austin"
$env:SESSION_SECRET= see .env-- the secret you created above

## Start backend
venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
python -m uvicorn app.main:app --port 8000 --reload

## Create a user
venv/Scripts/python -m app.cli.create_user testuser somepassword -- profile austin 


## start frontend
cd frontend 
npm run dev

## Create dynamodb table if it isn't created yet
aws dynamodb create-table --table-name User_Table --attribute-definitions AttributeName=username,AttributeType=S --key-schema AttributeName=username,KeyType=HASH --billing-mode PAY_PER_REQUEST --region us-east-1 --profile austin
