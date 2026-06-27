#!/usr/bin/env python3
"""
S3 Log Shipper
Runs via cron (every 5 min) on both Webserver and DB EC2 instances.
Ships logs to S3 bucket under logs/webserver/ or logs/db/
"""

import os, sys, boto3, datetime, logging, gzip, shutil

S3_BUCKET  = os.environ.get('S3_BUCKET')
S3_REGION  = os.environ.get('AWS_REGION')
NODE_TYPE  = os.environ.get('NODE_TYPE', 'webserver')   # 'webserver' or 'db'

LOG_PATHS = {
    'webserver': ['/var/log/webapp/app.log', '/var/log/nginx/access.log', '/var/log/nginx/error.log'],
    'db':        ['/var/log/mysql/error.log', '/var/log/mysql/mysql-slow.log'],
}

s3 = boto3.client('s3', region_name=S3_REGION)

def ship_logs():
    logs = LOG_PATHS.get(NODE_TYPE, [])
    ts   = datetime.datetime.utcnow().strftime('%Y/%m/%d/%H%M%S')

    for log_path in logs:
        if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
            continue
        fname   = os.path.basename(log_path)
        gz_path = f'/tmp/{fname}.gz'

        with open(log_path, 'rb') as f_in, gzip.open(gz_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        s3_key = f'logs/{NODE_TYPE}/{ts}/{fname}.gz'
        s3.upload_file(gz_path, S3_BUCKET, s3_key,
                       ExtraArgs={'StorageClass': 'STANDARD_IA'})
        print(f'Shipped {log_path} → s3://{S3_BUCKET}/{s3_key}')
        os.remove(gz_path)

if __name__ == '__main__':
    ship_logs()
