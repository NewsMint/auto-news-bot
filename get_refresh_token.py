import pickle
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/blogger']

def main():
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json', SCOPES)
    creds = flow.run_local_server(port=0)
    print("\n✅ REFRESH TOKEN:\n")
    print(creds.refresh_token)
    with open('token.pkl', 'wb') as token_file:
        pickle.dump(creds, token_file)

if __name__ == '__main__':
    main()
