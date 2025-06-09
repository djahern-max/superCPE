#!/bin/bash
# Save this as test_all.sh and run: chmod +x test_all.sh && ./test_all.sh

echo "Testing CPE Application..."

echo "1. Health Check:"
curl http://localhost:8000/health
echo -e "\n"

echo "2. Test Data:"
curl http://localhost:8000/test-data
echo -e "\n"

echo "3. Upload Sample Certificate:"
curl -X POST http://localhost:8000/upload-certificate/ \
  -F "file=@/Users/ryze.ai/Desktop/PDF_BOT/Certificate_9f535f09-574e-433d-9a5e-8fa362b7b7b8.pdf"
echo -e "\n"

echo "4. Process for CE Broker:"
curl -X POST http://localhost:8000/process-for-ce-broker/ \
  -H "Content-Type: application/json" \
  -d '{
    "course_name": "Debt: Selected Debt Related Issues",
    "course_code": "M116-2025-01-SSDL", 
    "field_of_study": "Taxes",
    "credits": 2.0,
    "completion_date": "2025-06-06"
  }'
echo -e "\n"

echo "Testing complete!"
