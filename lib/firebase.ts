// lib/firebase.ts
import { initializeApp, getApps, getApp } from "firebase/app";
import { getFirestore } from "firebase/firestore";

// Ensure all required environment variables are present for client-side Firebase setup.
// These are placeholders and should be set in your Vercel environment variables
// and a .env.local file for local development.
const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || "promisetrackerapp", // Default to your project ID if not set, but prefer env var
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID
};

// Check if all necessary Firebase config values are provided
let app;
const requiredConfigValues = [
  firebaseConfig.apiKey,
  firebaseConfig.authDomain,
  firebaseConfig.projectId,
  firebaseConfig.storageBucket,
  firebaseConfig.messagingSenderId,
  firebaseConfig.appId
];

const allConfigPresent = requiredConfigValues.every(value => value);

if (!allConfigPresent) {
  console.error(
    "Firebase configuration is incomplete. Please ensure all NEXT_PUBLIC_FIREBASE_ environment variables are set."
  );
  // Depending on your error handling strategy, you might throw an error here
  // or allow the app to continue, though Firebase services will likely fail.
}

// Initialize Firebase only if config is present
if (allConfigPresent) {
  if (!getApps().length) {
    app = initializeApp(firebaseConfig);
  } else {
    app = getApp();
  }
} else {
  // If config is not present, Firebase cannot be initialized.
  // Assign null or a mock/dummy app object if your app structure expects `app` to be defined.
  app = null; 
}

// Initialize Firestore only if Firebase app was successfully initialized
const db = app ? getFirestore(app) : null;

// You might want to export `app` as well if other Firebase services are needed elsewhere
export { db, app as firebaseApp }; 