import google.generativeai as genai

# Configure Gemini with your working API key
genai.configure(api_key="AIzaSyBiamstIK8spycFAfSNGwPkeTOKcF9RvKA")

# List available models
models = genai.list_models()

print("✅ Available Gemini Models for your API Key:\n")

for model in models:
    print(f"- {model.name}")
