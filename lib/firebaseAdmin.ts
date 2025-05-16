import * as admin from 'firebase-admin';

if (!admin.apps.length) {
  try {
    admin.initializeApp({
      // If you have GOOGLE_APPLICATION_CREDENTIALS set in your environment,
      // or are running in a GCP environment (like Cloud Run, Cloud Functions),
      // admin.credential.applicationDefault() will automatically find the credentials.
      //
      // For local development where GOOGLE_APPLICATION_CREDENTIALS is not set globally,
      // you would typically set this environment variable in your .env.local file or similar,
      // pointing to your service account key JSON file, e.g.:
      // GOOGLE_APPLICATION_CREDENTIALS=./path/to/your/serviceAccountKey.json
      //
      // And then applicationDefault() should still work.
      //
      // IMPORTANT: The recommended way for most environments is to use applicationDefault()
      // and ensure GOOGLE_APPLICATION_CREDENTIALS is set correctly in your environment.
      credential: admin.credential.applicationDefault(),
      // databaseURL: 'YOUR_DATABASE_URL' // if using Realtime Database
    });
  } catch (e) {
    console.error('Firebase admin initialization error', e);
  }
}

const firestoreAdmin = admin.firestore();

export { firestoreAdmin, admin as firebaseAdmin }; 