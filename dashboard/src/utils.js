/**
 * Utility functions for FinOps Cost Guardian Dashboard
 */

export function normalizeLambdaUrl(inputUrl) {
  let url = (inputUrl || '').trim().replace(/\/+$/, '');
  if (!url) return '';
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    url = 'https://' + url;
  }
  if (url.includes('.lambda-url.') && !url.includes('.on.aws')) {
    url = url + '.on.aws';
  }
  return url;
}

/**
 * Executes a fetch request with automatic fallback to local Vite proxy
 * if browser encounters a CORS duplicate header or network block.
 */
export async function smartFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);
    return response;
  } catch (directErr) {
    // If running on localhost/dev server, attempt request through Vite dev proxy
    if (typeof window !== 'undefined' && window.location.hostname === 'localhost') {
      try {
        const proxyUrl = `/api/proxy?url=${encodeURIComponent(url)}`;
        const proxyResponse = await fetch(proxyUrl, options);
        return proxyResponse;
      } catch (proxyErr) {
        throw directErr;
      }
    }
    throw directErr;
  }
}
