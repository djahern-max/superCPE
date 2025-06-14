"""
Digital Ocean Spaces integration for certificate storage
"""

import boto3
from botocore.exceptions import ClientError
import os
from typing import Optional, Dict
import hashlib
from datetime import datetime

class DOSpacesService:
    def __init__(self):
        self.spaces_client = boto3.client(
            's3',
            endpoint_url=f"https://{os.getenv('DO_SPACES_REGION', 'nyc3')}.digitaloceanspaces.com",
            aws_access_key_id=os.getenv('DO_SPACES_KEY'),
            aws_secret_access_key=os.getenv('DO_SPACES_SECRET'),
            region_name=os.getenv('DO_SPACES_REGION', 'nyc3')
        )
        self.bucket_name = os.getenv('DO_SPACES_BUCKET', 'supercpe-certificates')
    
    def upload_certificate(self, 
                          file_content: bytes, 
                          filename: str, 
                          user_id: int,
                          certificate_id: int) -> Dict[str, str]:
        """Upload certificate to DO Spaces with organized folder structure"""
        try:
            # Create organized path: certificates/user_123/2025/filename.pdf
            year = datetime.now().year
            key = f"certificates/user_{user_id}/{year}/{filename}"
            
            # Upload with metadata
            self.spaces_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=file_content,
                Metadata={
                    'user_id': str(user_id),
                    'certificate_id': str(certificate_id),
                    'upload_date': datetime.now().isoformat(),
                    'file_hash': hashlib.sha256(file_content).hexdigest()
                },
                ContentType='application/pdf'
            )
            
            # Generate public URL
            url = f"https://{self.bucket_name}.{os.getenv('DO_SPACES_REGION', 'nyc3')}.digitaloceanspaces.com/{key}"
            
            return {
                'status': 'success',
                'url': url,
                'key': key,
                'bucket': self.bucket_name
            }
            
        except ClientError as e:
            return {
                'status': 'error',
                'error': str(e),
                'key': None,
                'url': None
            }
    
    def delete_certificate(self, key: str) -> bool:
        """Delete certificate from DO Spaces"""
        try:
            self.spaces_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """Generate temporary download URL"""
        try:
            response = self.spaces_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return response
        except ClientError:
            return None
