import { useRouter } from 'expo-router';
import ConversationsScreen from '../../src/screens/ConversationsScreen';

export default function Page() {
  const router = useRouter();
  return <ConversationsScreen onSelect={() => router.push('/(tabs)/')} />;
}
