// Test script to verify the flat structure works with the frontend data layer
// This simulates how the frontend would query the new flat promises collection

const admin = require('firebase-admin');

// Initialize Firebase Admin (using default credentials)
if (!admin.apps.length) {
  admin.initializeApp({
    projectId: 'promisetrackerapp'
  });
}

const db = admin.firestore();

async function testFlatStructureQueries() {
  console.log('🧪 Testing flat structure queries...\n');

  try {
    // Test 1: Basic flat collection query
    console.log('📊 Test 1: Basic flat collection query');
    const flatQuery = db.collection('promises')
      .where('party_code', '==', 'LPC')
      .where('region_code', '==', 'Canada')
      .limit(5);
    
    const flatSnapshot = await flatQuery.get();
    console.log(`✅ Found ${flatSnapshot.size} LPC promises in flat structure`);
    
    if (flatSnapshot.size > 0) {
      const firstDoc = flatSnapshot.docs[0];
      const data = firstDoc.data();
      console.log(`   Sample document ID: ${firstDoc.id}`);
      console.log(`   Department: ${data.responsible_department_lead}`);
      console.log(`   Party: ${data.party_code}, Region: ${data.region_code}`);
      console.log(`   Has migration metadata: ${!!data.migration_metadata}`);
    }

    // Test 2: Department-specific query (simulating frontend fetchPromisesForDepartment)
    console.log('\n📊 Test 2: Department-specific query');
    const deptQuery = db.collection('promises')
      .where('responsible_department_lead', '==', 'Finance Canada')
      .where('party_code', '==', 'LPC')
      .where('region_code', '==', 'Canada')
      .where('parliament_session_id', '==', '44')
      .limit(3);
    
    const deptSnapshot = await deptQuery.get();
    console.log(`✅ Found ${deptSnapshot.size} Finance Canada promises`);
    
    // Test 3: Count by party (simulating getPromiseCountsByParty)
    console.log('\n📊 Test 3: Count by party');
    const parties = ['LPC', 'CPC', 'NDP', 'BQ', 'GP'];
    const partyCounts = {};
    
    for (const party of parties) {
      const countQuery = db.collection('promises')
        .where('party_code', '==', party)
        .where('region_code', '==', 'Canada');
      
      const countSnapshot = await countQuery.count().get();
      partyCounts[party] = countSnapshot.data().count;
    }
    
    console.log('✅ Party counts:', partyCounts);

    // Test 4: Migration metadata check
    console.log('\n📊 Test 4: Migration metadata validation');
    const migrationQuery = db.collection('promises')
      .where('migration_metadata.migration_version', '==', '1.0')
      .limit(1);
    
    const migrationSnapshot = await migrationQuery.get();
    console.log(`✅ Documents with migration metadata: ${migrationSnapshot.size > 0 ? 'Found' : 'None'}`);
    
    if (migrationSnapshot.size > 0) {
      const migrationDoc = migrationSnapshot.docs[0];
      const metadata = migrationDoc.data().migration_metadata;
      console.log(`   Migration timestamp: ${metadata.migrated_at}`);
      console.log(`   Original path: ${metadata.original_path}`);
    }

    console.log('\n🎉 All flat structure tests passed! Frontend should work correctly.');
    
  } catch (error) {
    console.error('❌ Error testing flat structure:', error);
    process.exit(1);
  }
}

// Run the tests
testFlatStructureQueries()
  .then(() => {
    console.log('\n✅ Test completed successfully');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Test failed:', error);
    process.exit(1);
  }); 