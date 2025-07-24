#!/bin/bash

# Test Entity Research Crew via API

# Configuration
API_URL="https://crew-api.railway.app/crew_job"
CLIENT_USER_ID="587f8370-825f-4f0c-8846-2e6d70782989"
ACTOR_ID="1131ca9d-35d8-4ad1-ad77-0485b0239b86"  # Reid the CFO synth
ACTOR_TYPE="synth"

# You need to set your JWT token here
JWT_TOKEN="${JWT_TOKEN:-your-jwt-token-here}"

# Create the request payload
REQUEST_JSON=$(cat <<EOF
{
  "crew_name": "entity_research_crew",
  "job_key": "entity_research_openai_$(date +%s)",
  "client_user_id": "${CLIENT_USER_ID}",
  "actor_type": "${ACTOR_TYPE}",
  "actor_id": "${ACTOR_ID}",
  "context": {
    "entity_name": "OpenAI",
    "entity_domain": "technology",
    "research_depth": "comprehensive",
    "focus_areas": [
      "leadership team",
      "recent developments",
      "product offerings",
      "partnerships",
      "funding history"
    ]
  }
}
EOF
)

echo "🚀 Submitting Entity Research Crew job..."
echo "📋 Request payload:"
echo "${REQUEST_JSON}" | jq .

# Make the API call
RESPONSE=$(curl -X POST "${API_URL}" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${REQUEST_JSON}" \
  -s -w "\n\nHTTP_STATUS:%{http_code}")

# Extract HTTP status
HTTP_STATUS=$(echo "${RESPONSE}" | tail -n 1 | cut -d: -f2)
RESPONSE_BODY=$(echo "${RESPONSE}" | sed '$d')

echo -e "\n📡 Response:"
echo "${RESPONSE_BODY}" | jq .

echo -e "\n📊 HTTP Status: ${HTTP_STATUS}"

# If successful, extract job_id
if [ "${HTTP_STATUS}" = "200" ] || [ "${HTTP_STATUS}" = "201" ]; then
    JOB_ID=$(echo "${RESPONSE_BODY}" | jq -r '.job_id')
    echo -e "\n✅ Job submitted successfully!"
    echo "📌 Job ID: ${JOB_ID}"
    echo -e "\n🔍 To check job status:"
    echo "curl -H \"Authorization: Bearer \${JWT_TOKEN}\" ${API_URL}/${JOB_ID}"
else
    echo -e "\n❌ Job submission failed!"
    exit 1
fi

exit 0
