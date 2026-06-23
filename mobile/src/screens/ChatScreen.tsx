import React, { useState, useRef, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator,
  SafeAreaView,
} from 'react-native';
import { chatStream } from '../api/client';
import { COLORS, RADIUS } from '../theme';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatScreen() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const listRef = useRef<FlatList>(null);
  const iaIdRef = useRef<string | null>(null);

  const envoyer = useCallback(async () => {
    const texte = input.trim();
    if (!texte || loading) return;
    setInput('');

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: texte };
    const iaId = (Date.now() + 1).toString();
    iaIdRef.current = iaId;

    setMessages(prev => [...prev, userMsg, { id: iaId, role: 'assistant', content: '' }]);
    setLoading(true);

    try {
      await chatStream(
        texte, convId,
        (delta) => {
          setMessages(prev =>
            prev.map(m => m.id === iaId ? { ...m, content: m.content + delta } : m)
          );
        },
        (id) => setConvId(id)
      );
    } catch (e) {
      setMessages(prev =>
        prev.map(m => m.id === iaId ? { ...m, content: 'Erreur : impossible de joindre le serveur.' } : m)
      );
    }
    setLoading(false);
  }, [input, loading, convId]);

  const renderMsg = ({ item }: { item: Message }) => (
    <View style={[styles.bubble, item.role === 'user' ? styles.bubbleUser : styles.bubbleIA]}>
      <Text style={[styles.bubbleText, item.role === 'user' && styles.bubbleTextUser]}>
        {item.content || (item.role === 'assistant' ? '…' : '')}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>UNION IA</Text>
        {loading && <ActivityIndicator size="small" color={COLORS.accent} />}
      </View>

      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={m => m.id}
        renderItem={renderMsg}
        contentContainerStyle={styles.list}
        onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>👋 Bonjour ! Comment puis-je t'aider ?</Text>
          </View>
        }
      />

      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'}>
        <View style={styles.inputZone}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Écris un message…"
            placeholderTextColor={COLORS.muted}
            multiline
            maxLength={4000}
            onSubmitEditing={envoyer}
            returnKeyType="send"
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || loading) && styles.sendBtnDisabled]}
            onPress={envoyer}
            disabled={!input.trim() || loading}
          >
            <Text style={styles.sendBtnText}>↑</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  headerTitle: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  list: { padding: 12, gap: 8, flexGrow: 1 },
  bubble: { maxWidth: '85%', padding: 10, borderRadius: RADIUS.md, marginVertical: 3 },
  bubbleUser: { backgroundColor: COLORS.accent, alignSelf: 'flex-end' },
  bubbleIA: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, alignSelf: 'flex-start' },
  bubbleText: { color: COLORS.text, fontSize: 15, lineHeight: 21 },
  bubbleTextUser: { color: '#fff' },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyText: { color: COLORS.muted, fontSize: 15 },
  inputZone: {
    flexDirection: 'row', alignItems: 'flex-end', padding: 10, gap: 8,
    borderTopWidth: 1, borderTopColor: COLORS.border, backgroundColor: COLORS.surface,
  },
  input: {
    flex: 1, backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: RADIUS.md, padding: 10, color: COLORS.text, fontSize: 15,
    maxHeight: 120, minHeight: 42,
  },
  sendBtn: {
    width: 42, height: 42, borderRadius: 21, backgroundColor: COLORS.accent,
    alignItems: 'center', justifyContent: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendBtnText: { color: '#fff', fontSize: 20, fontWeight: '700' },
});
