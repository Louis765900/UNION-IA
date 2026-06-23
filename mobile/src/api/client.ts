import AsyncStorage from '@react-native-async-storage/async-storage';

const DEFAULT_URL = 'http://127.0.0.1:5000';

export async function getServerUrl(): Promise<string> {
  return (await AsyncStorage.getItem('server_url')) || DEFAULT_URL;
}

export async function getToken(): Promise<string> {
  return (await AsyncStorage.getItem('auth_token')) || '';
}

async function headers(): Promise<Record<string, string>> {
  const token = await getToken();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

export async function apiGet(path: string) {
  const url = await getServerUrl();
  const r = await fetch(`${url}${path}`, { headers: await headers() });
  return r.json();
}

export async function apiPost(path: string, body: object) {
  const url = await getServerUrl();
  const r = await fetch(`${url}${path}`, {
    method: 'POST',
    headers: await headers(),
    body: JSON.stringify(body),
  });
  return r.json();
}

export async function login(email: string, password: string): Promise<{ success: boolean; token?: string; error?: string; user?: any }> {
  const data = await apiPost('/api/auth/login', { email, password });
  if (data.success && data.token) {
    await AsyncStorage.setItem('auth_token', data.token);
  }
  return data;
}

export async function logout() {
  await apiPost('/api/auth/logout', {});
  await AsyncStorage.removeItem('auth_token');
}

// Chat en streaming — retourne chaque fragment via onDelta
export async function chatStream(
  message: string,
  convId: string | null,
  onDelta: (text: string) => void,
  onConvId: (id: string) => void
): Promise<void> {
  const url = await getServerUrl();
  const token = await getToken();
  const h: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) h['Authorization'] = `Bearer ${token}`;

  const r = await fetch(`${url}/api/chat`, {
    method: 'POST',
    headers: h,
    body: JSON.stringify({ message, conversation_id: convId }),
  });

  if (!r.body) throw new Error('Pas de body SSE');

  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() || '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const evt = JSON.parse(line.slice(6));
        if (evt.phase === 'conversation') onConvId(evt.content);
        else if (evt.phase === 'repondre') onDelta(evt.content);
      } catch {}
    }
  }
}
