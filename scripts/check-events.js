// scripts/check-events.js
import RSSParser from 'rss-parser';

const RSS_FEED_URL = 'https://rss.app/feeds/v1.1/YOUR_BATTLEFIELD_RSS_ID.json'; // Replace with your feed bridge URL
const WORKER_URL = process.env.WORKER_URL;
const WORKER_SECRET = process.env.WORKER_SECRET;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY; // Or OPENAI_API_KEY

async function analyzeWithAI(title, content) {
  const prompt = `
You are an automated game event monitoring assistant. Review this social media post text from the official Battlefield account:

Title: ${title}
Content: ${content}

Task: Determine if this post announces a major in-game promotional event, such as a "Free Trial", "Free Weekend", "Double XP", or a new "Season Launch". Ignore general community clips or sweepstakes.

If a genuine event is active, extract the exact event name, the start timestamp, the end timestamp (in ISO format YYYY-MM-DDTHH:mm:ssZ if available, or null), and assign an event traffic multiplier (e.g., Free Trial = 1.6, Double XP = 1.35).

Output your response strictly as a valid JSON object with no markdown code blocks or backticks:
{
  "event_active": true/false,
  "event_type": "Name of event or null",
  "start_date": "YYYY-MM-DDTHH:mm:ssZ or null",
  "end_date": "YYYY-MM-DDTHH:mm:ssZ or null",
  "multiplier": 1.0
}
`;

  // Example using Gemini API endpoint (or swap for OpenAI endpoint)
  const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }]
    })
  });

  const data = await response.json();
  const rawText = data.candidates?.[0]?.content?.parts?.[0]?.text || '{}';
  
  // Clean up any stray markdown formatting if the model adds it
  const cleanedJSON = rawText.replace(/```json/g, '').replace(/```/g, '').trim();
  return JSON.parse(cleanedJSON);
}

async function run() {
  const parser = new RSSParser();
  console.log('Fetching Battlefield feed...');
  const feed = await parser.parseURL(RSS_FEED_URL);

  // Check the most recent post
  const latestItem = feed.items[0];
  if (!latestItem) {
    console.log('No feed items found.');
    return;
  }

  console.log(`Analyzing latest post: "${latestItem.title}"`);
  const eventData = await analyzeWithAI(latestItem.title, latestItem.contentSnippet || latestItem.content);

  console.log('Parsed Event Data:', eventData);

  if (eventData.event_active) {
    console.log('Sending event update to Cloudflare D1 Backend...');
    const res = await fetch(WORKER_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${WORKER_SECRET}`
      },
      body: JSON.stringify(eventData)
    });
    
    if (res.ok) {
      console.log('Successfully updated D1 database via Worker!');
    } else {
      console.error('Failed to update backend:', await res.text());
    }
  } else {
    console.log('No active promotional event detected in this post.');
  }
}

run().catch(err => {
  console.error('Error running script:', err);
  process.exit(1);
});
