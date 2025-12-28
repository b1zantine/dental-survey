/*
To complete the Google Sheets setup, you need to:
1. Create a Google Sheet with appropriate columns
2. Go to Extensions > Apps Script
3. Add this code to your Apps Script and save it
4. Deploy as Web App (Execute as: Me, Access: Anyone)
5. Copy the URL and replace YOUR_GOOGLE_APPS_SCRIPT_URL_HERE in index.html
*/

function doPost(e) {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const data = JSON.parse(e.postData.contents);
    
    // Append row with all data fields
    sheet.appendRow([
      data.timestamp, data.duration, data.age, data.gender, data.experience,
      data.locality, data.workType, data.designation, data.gumTreatment,
      data.treatments, data.treatments_other, data.knowledgeScore, data.knowledgeTotal,
      data.k1, data.k2, data.k3, data.k4, data.k5, data.k6, data.k7, data.k8, data.k9, data.k10,
      data.a1, data.a2, data.a3, data.a4, data.a5, data.a6, data.a7, data.a8, data.a9, data.a10,
      data.p1, data.p2, data.p3, data.p4, data.p5, data.p6, data.p7, data.p8, data.p9, data.p10
    ]);
    
    return ContentService.createTextOutput('Success');
}
