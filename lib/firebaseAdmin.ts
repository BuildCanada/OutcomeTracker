import admin from "firebase-admin";

console.log("ADMIN", admin.apps.length);

if (!admin.apps.length) {
  // try {
  const serviceAccountEnv = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  if (serviceAccountEnv) {
    const serviceAccount = JSON.parse(serviceAccountEnv);
    console.log("GOING!", admin.credential.cert(serviceAccount));
    admin.initializeApp({
      credential: admin.credential.cert(serviceAccount),
      // Optionally, you can explicitly set projectId if needed, though cert() usually infers it.
      // projectId: serviceAccount.project_id,
    });
    console.log(
      "Firebase Admin SDK initialized successfully using GOOGLE_APPLICATION_CREDENTIALS environment variable content.",
    );
  } else {
    // Fallback for environments where GOOGLE_APPLICATION_CREDENTIALS might be a path or not set (e.g. local dev using ADC)
    console.warn(
      "GOOGLE_APPLICATION_CREDENTIALS environment variable not found or empty. " +
        "Attempting default initialization (this is expected for local development with gcloud CLI setup, " +
        "but might fail on Vercel if the variable was expected to contain JSON content).",
    );
    admin.initializeApp(); // Default ADC: useful for local dev, Cloud Run, Cloud Functions
  }
  // } catch (e) {
  //   console.error("Firebase admin initialization error", e);
  //   // Enhanced error logging
  //   if (e instanceof Error) {
  //     console.error("Error name:", e.name);
  //     console.error("Error message:", e.message);
  //     console.error("Error stack:", e.stack);
  //   }
  //   // Attempt to log code if present (common in Firebase/Google errors)
  //   if (typeof e === "object" && e !== null && "code" in e) {
  //     console.error("Error code:", (e as { code: string }).code);
  //   }
  // }
}

const firestoreAdmin = admin.firestore();

export { firestoreAdmin, admin as firebaseAdmin };
