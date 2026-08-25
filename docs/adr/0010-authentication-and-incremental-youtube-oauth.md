# 0010: Authentication and Incremental YouTube OAuth Authorization

## Context
Croviq requires user authentication to secure Workspace data and authorization to interact with YouTube APIs (for uploading videos, syncing metadata, and reading analytics). Requesting extensive YouTube write permissions upfront during initial account sign-up increases user friction and violates the principle of least privilege.

## Decision
We decouple authentication from external platform authorization:
1. **User Identity & Session (Firebase Auth)**: Firebase Authentication with Google Sign-In provides user authentication, session tokens, and native integration with Google Cloud Firestore security rules.
2. **Incremental YouTube OAuth**: YouTube channel integration is an explicit, secondary "Connect Channel" action within the Workspace settings. The creator grants YouTube Data API OAuth scopes only when enabling automated publishing or analytics syncing.
3. **Token Management**: YouTube OAuth refresh tokens and credentials are securely encrypted and stored per Workspace in Google Secret Manager / Firestore private credentials subcollections, isolated from general application logs and client payloads.

## Consequences
- Frictionless, trustworthy onboarding for new creators.
- Adheres to least privilege security practices.
- Seamless IAM and security rule integration between Firebase Auth and Firestore.
