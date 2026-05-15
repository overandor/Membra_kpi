export default function handler(request, response) {
  response.setHeader('Access-Control-Allow-Origin', '*');
  response.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  response.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (request.method === 'OPTIONS') {
    response.status(204).end();
    return;
  }
  response.status(200).json({
    app: 'MEMBRA KPI Vercel Frontend',
    apiBase: process.env.MEMBRA_API_BASE || '',
    message: 'Set MEMBRA_API_BASE in Vercel env or use dashboard ?api=https://backend-url.'
  });
}
