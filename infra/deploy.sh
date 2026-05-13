#!/bin/bash
# Deploy script - run from project root
# Usage: ./infra/deploy.sh <EC2_IP> <KEY_PATH>

EC2_IP=$1
KEY_PATH=$2

if [ -z "$EC2_IP" ] || [ -z "$KEY_PATH" ]; then
  echo "Usage: ./infra/deploy.sh <EC2_IP> <KEY_PATH>"
  echo "Example: ./infra/deploy.sh 54.123.45.67 ~/.ssh/my-key.pem"
  exit 1
fi

echo "Deploying to $EC2_IP..."

# Sync code to EC2
rsync -avz --exclude='venv' --exclude='__pycache__' --exclude='.git' --exclude='uploads' \
  -e "ssh -i $KEY_PATH" \
  . ec2-user@$EC2_IP:/opt/vsportmanager/

# Install dependencies and restart
ssh -i $KEY_PATH ec2-user@$EC2_IP << 'EOF'
  cd /opt/vsportmanager
  
  # Load env vars
  export $(cat .env | xargs)
  
  # Install/update dependencies
  pip3.11 install -r requirements.txt
  
  # Kill existing process
  pkill -f "uvicorn app.main:app" || true
  
  # Start API in background
  nohup python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /var/log/vsportmanager.log 2>&1 &
  
  echo "API deployed and running on port 8000"
EOF
