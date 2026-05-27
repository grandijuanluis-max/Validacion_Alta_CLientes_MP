import os
from supabase import create_client

url = "https://sspjbsbuklqiekvxgdtc.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNzcGpic2J1a2xxaWVrdnhnZHRjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg4Nzk5OTEsImV4cCI6MjA5NDQ1NTk5MX0.grOUFUOXytYGJwk0A3krFFY6Ms2Igo7XymYhe49N8xA"
supabase = create_client(url, key)

res = supabase.table("ramos").select("*").limit(2).execute()
print("Ramos:", res.data)

res2 = supabase.table("codigos_postales").select("*").limit(2).execute()
print("CP:", res2.data)
