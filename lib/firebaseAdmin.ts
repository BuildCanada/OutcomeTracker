import admin from "firebase-admin";
import fs from "fs"; // Import fs

if (!admin.apps.length) {
  const credsEnvVar = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  try {
    if (credsEnvVar) {
      try {
        // Attempt to parse as JSON string (e.g., if pasted directly into Vercel env vars)
        const serviceAccount = JSON.parse(credsEnvVar);
        admin.initializeApp({
          credential: admin.credential.cert(serviceAccount),
        });
        console.log(
          "Firebase Admin SDK initialized using GOOGLE_APPLICATION_CREDENTIALS as JSON string.",
        );
      } catch (e) {
        // If JSON.parse fails, assume it's a file path
        //console.log("GOOGLE_APPLICATION_CREDENTIALS is not a JSON string, assuming it's a file path. Attempting to read file...");
        const serviceAccountFileContent = fs.readFileSync(credsEnvVar, "utf8");
        const serviceAccount = JSON.parse(serviceAccountFileContent);
        admin.initializeApp({
          credential: admin.credential.cert(serviceAccount),
        });
        //console.log("Firebase Admin SDK initialized by reading file from GOOGLE_APPLICATION_CREDENTIALS path.");
      }
    } else {
      // GOOGLE_APPLICATION_CREDENTIALS is not set, try default ADC
      console.log(
        "GOOGLE_APPLICATION_CREDENTIALS not set. Attempting default ADC initialization.",
      );
      admin.initializeApp();
    }
  } catch (error) {
    console.error("Firebase admin initialization error:", error);
    if (error instanceof Error) {
      console.error(`Error Name: ${error.name}`);
      console.error(`Error Message: ${error.message}`);
      console.error(`Error Stack: ${error.stack}`);
    }
    if (typeof error === "object" && error !== null && "code" in error) {
      console.error(`Error Code: ${(error as { code: string }).code}`);
    }
  }
}

const firestoreAdmin = admin.firestore();

export { firestoreAdmin };
