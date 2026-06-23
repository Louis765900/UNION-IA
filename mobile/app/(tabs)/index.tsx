import React, { useState } from 'react';
import ChatScreen from '../../src/screens/ChatScreen';

export default function Page() {
  const [convId, setConvId] = useState<string | null>(null);
  return <ChatScreen convId={convId} onConvId={setConvId} />;
}
