/**
 * Migration Script: Add status field to all existing promises
 * 
 * This script adds a 'status' field with value 'active' to all existing promises
 * that don't already have a status field.
 * 
 * Usage: node scripts/migrate_add_status_field.js
 */

const admin = require('firebase-admin');
const path = require('path');
const fs = require('fs');

// Load environment variables from .env file
function loadEnvFile() {
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    envContent.split('\n').forEach(line => {
      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length > 0) {
        const value = valueParts.join('=').trim();
        // Remove quotes if present
        const cleanValue = value.replace(/^["']|["']$/g, '');
        process.env[key.trim()] = cleanValue;
      }
    });
    console.log('✅ Loaded .env file');
  } else {
    console.log('⚠️  No .env file found, using system environment variables');
  }
}

/**
 * Initialize Firebase Admin SDK with robust credential handling
 * Based on the pattern from consolidated_promise_enrichment.py
 */
function initializeFirebase() {
  // Load .env file first
  loadEnvFile();
  
  if (admin.apps.length > 0) {
    console.log('✅ Firebase already initialized');
    return admin.firestore();
  }

  console.log('🔧 Initializing Firebase Admin SDK...');

  // PHASE 1: Try default credentials with explicit project ID
  try {
    const projectId = process.env.FIREBASE_PROJECT_ID;
    console.log(`🔍 Using project ID: ${projectId}`);
    
    const initOptions = {};
    if (projectId) {
      initOptions.projectId = projectId;
    }
    
    admin.initializeApp(initOptions);
    console.log(`✅ Connected to CLOUD Firestore (Project: ${projectId || '[Auto-detected]'}) using default credentials.`);
    return admin.firestore();
  } catch (error) {
    console.warn(`⚠️  Default credentials failed: ${error.message}. Attempting service account...`);
    
    // Clean up the failed app
    if (admin.apps.length > 0) {
      admin.apps[0].delete();
    }
  }

  // PHASE 2: Try GOOGLE_APPLICATION_CREDENTIALS path
  if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
    try {
      console.log(`🔑 Attempting Firebase init with GOOGLE_APPLICATION_CREDENTIALS: ${process.env.GOOGLE_APPLICATION_CREDENTIALS}`);
      
      if (!fs.existsSync(process.env.GOOGLE_APPLICATION_CREDENTIALS)) {
        throw new Error(`Service account file not found at: ${process.env.GOOGLE_APPLICATION_CREDENTIALS}`);
      }
      
      const serviceAccount = require(process.env.GOOGLE_APPLICATION_CREDENTIALS);
      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
        projectId: process.env.FIREBASE_PROJECT_ID || serviceAccount.project_id
      });
      
      const projectId = process.env.FIREBASE_PROJECT_ID || serviceAccount.project_id || '[Not Set - Using Service Account]';
      console.log(`✅ Connected to CLOUD Firestore (Project: ${projectId}) via GOOGLE_APPLICATION_CREDENTIALS.`);
      return admin.firestore();
    } catch (error) {
      console.error(`❌ GOOGLE_APPLICATION_CREDENTIALS initialization failed: ${error.message}`);
      
      // Clean up the failed app
      if (admin.apps.length > 0) {
        admin.apps[0].delete();
      }
    }
  }

  // PHASE 3: Try service account key from environment variable (JSON string)
  if (process.env.FIREBASE_SERVICE_ACCOUNT_KEY) {
    try {
      console.log('🔑 Attempting Firebase init with service account key from FIREBASE_SERVICE_ACCOUNT_KEY...');
      const serviceAccount = JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_KEY);
      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
      });
      const projectId = process.env.FIREBASE_PROJECT_ID || serviceAccount.project_id || '[Not Set - Using Service Account]';
      console.log(`✅ Connected to CLOUD Firestore (Project: ${projectId}) via service account (JSON key).`);
      return admin.firestore();
    } catch (error) {
      console.error(`❌ Service account JSON key initialization failed: ${error.message}`);
      
      // Clean up the failed app
      if (admin.apps.length > 0) {
        admin.apps[0].delete();
      }
    }
  }

  // PHASE 4: Try service account key file path
  if (process.env.FIREBASE_SERVICE_ACCOUNT_KEY_PATH) {
    try {
      console.log(`🔑 Attempting Firebase init with service account key file: ${process.env.FIREBASE_SERVICE_ACCOUNT_KEY_PATH}`);
      const serviceAccount = require(process.env.FIREBASE_SERVICE_ACCOUNT_KEY_PATH);
      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
      });
      const projectId = process.env.FIREBASE_PROJECT_ID || serviceAccount.project_id || '[Not Set - Using Service Account]';
      console.log(`✅ Connected to CLOUD Firestore (Project: ${projectId}) via service account (file path).`);
      return admin.firestore();
    } catch (error) {
      console.error(`❌ Service account key file initialization failed: ${error.message}`);
      
      // Clean up the failed app
      if (admin.apps.length > 0) {
        admin.apps[0].delete();
      }
    }
  }

  // PHASE 5: Final fallback with alternative environment variable names
  if (process.env.FIREBASE_ADMIN_SDK_PATH) {
    try {
      console.log(`🔑 Attempting Firebase init with alternative path: ${process.env.FIREBASE_ADMIN_SDK_PATH}`);
      const serviceAccount = require(process.env.FIREBASE_ADMIN_SDK_PATH);
      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
      });
      const projectId = process.env.FIREBASE_PROJECT_ID || serviceAccount.project_id || '[Not Set - Using Alt Service Account]';
      console.log(`✅ Connected to CLOUD Firestore (Project: ${projectId}) via alternative service account.`);
      return admin.firestore();
    } catch (error) {
      console.error(`❌ Alternative service account initialization failed: ${error.message}`);
    }
  }

  // If we get here, all initialization attempts failed
  console.error('❌ CRITICAL: Failed to obtain Firestore client. All credential methods failed.');
  console.error('Please ensure one of the following:');
  console.error('1. Running in Google Cloud environment with default credentials');
  console.error('2. GOOGLE_APPLICATION_CREDENTIALS environment variable is set (file path)');
  console.error('3. FIREBASE_SERVICE_ACCOUNT_KEY environment variable is set (JSON string)');
  console.error('4. FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable is set (file path)');
  console.error('5. FIREBASE_ADMIN_SDK_PATH environment variable is set');
  
  process.exit(1);
}

// Initialize Firebase and get Firestore client
const db = initializeFirebase();

async function migratePromisesStatus() {
  console.log('🚀 Starting migration: Adding status field to promises...');
  
  try {
    // Get all promises from the flat collection
    const promisesRef = db.collection('promises');
    
    // Process in batches to avoid memory issues
    const batchSize = 500;
    let lastDoc = null;
    let totalProcessed = 0;
    let totalUpdated = 0;
    
    while (true) {
      console.log(`📦 Processing batch starting from ${lastDoc ? lastDoc.id : 'beginning'}...`);
      
      let query = promisesRef.limit(batchSize);
      if (lastDoc) {
        query = query.startAfter(lastDoc);
      }
      
      const snapshot = await query.get();
      
      if (snapshot.empty) {
        console.log('✅ No more documents to process');
        break;
      }
      
      // Create batch for updates
      const batch = db.batch();
      let batchUpdateCount = 0;
      
      snapshot.docs.forEach(doc => {
        const data = doc.data();
        totalProcessed++;
        
        // Check if status field is missing or undefined
        if (!data.status) {
          batch.update(doc.ref, {
            status: 'active',
            migration_status_added_at: admin.firestore.FieldValue.serverTimestamp(),
            migration_version: '1.0'
          });
          batchUpdateCount++;
          totalUpdated++;
        }
      });
      
      // Commit the batch if there are updates
      if (batchUpdateCount > 0) {
        await batch.commit();
        console.log(`✅ Updated ${batchUpdateCount} documents in this batch`);
      } else {
        console.log(`ℹ️  No updates needed for this batch`);
      }
      
      // Set up for next iteration
      lastDoc = snapshot.docs[snapshot.docs.length - 1];
      
      // Add a small delay to be nice to Firestore
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    console.log('\n🎉 Migration completed successfully!');
    console.log(`📊 Summary:`);
    console.log(`   - Total promises processed: ${totalProcessed}`);
    console.log(`   - Total promises updated: ${totalUpdated}`);
    console.log(`   - Promises that already had status: ${totalProcessed - totalUpdated}`);
    
  } catch (error) {
    console.error('❌ Migration failed:', error);
    process.exit(1);
  }
}

// Verification function to check migration results
async function verifyMigration() {
  console.log('\n🔍 Verifying migration results...');
  
  try {
    const promisesRef = db.collection('promises');
    
    // Count total promises
    const totalSnapshot = await promisesRef.count().get();
    const totalCount = totalSnapshot.data().count;
    
    // Count promises with status = 'active'
    const activeSnapshot = await promisesRef.where('status', '==', 'active').count().get();
    const activeCount = activeSnapshot.data().count;
    
    // Count promises with status = 'deleted'
    const deletedSnapshot = await promisesRef.where('status', '==', 'deleted').count().get();
    const deletedCount = deletedSnapshot.data().count;
    
    // Count promises without status field
    const noStatusSnapshot = await promisesRef.where('status', '==', null).count().get();
    const noStatusCount = noStatusSnapshot.data().count;
    
    console.log(`📊 Verification Results:`);
    console.log(`   - Total promises: ${totalCount}`);
    console.log(`   - Active promises: ${activeCount}`);
    console.log(`   - Deleted promises: ${deletedCount}`);
    console.log(`   - Promises without status: ${noStatusCount}`);
    
    if (noStatusCount > 0) {
      console.log(`⚠️  Warning: ${noStatusCount} promises still don't have a status field`);
    } else {
      console.log(`✅ All promises now have a status field!`);
    }
    
  } catch (error) {
    console.error('❌ Verification failed:', error);
  }
}

// Main execution
async function main() {
  try {
    await migratePromisesStatus();
    await verifyMigration();
    console.log('\n🏁 Migration script completed');
    process.exit(0);
  } catch (error) {
    console.error('❌ Script failed:', error);
    process.exit(1);
  }
}

// Run the migration if this script is executed directly
if (require.main === module) {
  main();
}

module.exports = {
  migratePromisesStatus,
  verifyMigration
}; 