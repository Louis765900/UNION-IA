import React, { useState, useRef, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, KeyboardAvoidingView, Platform, ActivityIndicator,
  SafeAreaView, Pressable,
} from 'react-native';
import { chatStream } from '../api/client';
import { COLORS, RADIUS } from '../theme';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  done?: boolean;
}

interface Props {
  convId: string | null;
  onConvId: (id: string) => void;
}

export default function ChatScreen({ convId, onConvId }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef<FlatList>(null);

  const envoyer = useCallback(async () => {
    const texte = input.trim();
    if (!texte || loading) return;
    setInput('');

    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: texte, done: true };
    const iaId = (Date.now() + 1).toString();
    setMessages(prev => [...prev, userMsg, { id: iaId, role: 'assistant', content: '', done: false }]);
    setLoading(true);

    try {
      await chatStream(
        texte, convId,
        (delta, phase) => {
          setMessages(prev => prev.map(m => {
            if (m.id !== iaId) return m;
            if (phase === 'think') return { ...m, thinking: (m.thinking || '') + delta };
            return { ...m, content: m.content + delta };
          }));
        },
        (id) => onConvId(id),
      );
      setMessages(prev => prev.map(m => m.id === iaId ? { ...m, done: true } : m));
    } catch {
      setMessages(prev => prev.map(m =>
        m.id === iaId ? { ...m, content: 'Erreur : impossible de joindre le serveur.', done: true } : m
      ));
    }
    setLoading(false);
  }, [input, loading, convId, onConvId]);

  const renderMsg = ({ item }: { item: Message }) => (
    <View style={[styles.bubble, item.role === 'user' ? styles.bubbleUser : styles.bubbleIA]}>
      {item.thinking ? (
        <Text style={styles.thinkText}>💭 {item.thinking.length > 120 ? item.thinking.slice(0, 120) + '…' : item.thinking}</Text>
      ) : null}
      <Text style={[styles.bubbleText, item.role === 'user' && styles.bubbleTextUser]}>
        {item.content || (!item.done && item.role === 'assistant' ? '…' : '')}
      </Text>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>UNION IA</Text>
        <View style={styles.headerRight}>
          {loading && <ActivityIndicator size="small" color={COLORS.accent} style={{ marginRight: 8 }} />}
          {messages.length > 0 && (
            <Pressable onPress={() => { setMessages([]); onConvId(''); }} style={styles.newBtn}>
              <Text style={styles.newBtnTxt}>+ Nouveau</Text>
            </Pressable>
          )}
        </View>
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
            <Text style={styles.emptyEmoji}>✦</Text>
            <Text style={styles.emptyTitle}>UNION IA</Text>
            <Text style={styles.emptyText}>Assistant IA personnel</Text>
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
    paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    backgroundColor: COLORS.surface,
  },
  headerTitle: { fontSize: 17, fontWeight: '700', color: COLORS.text },
  headerRight: { flexDirection: 'row', alignItems: 'center' },
  newBtn: {
    backgroundColor: 'rgba(124,111,247,.15)', borderRadius: RADIUS.sm,
    paddingHorizontal: 10, paddingVertical: 5,
  },
  newBtnTxt: { color: COLORS.accent, fontSize: 13, fontWeight: '600' },
  list: { padding: 12, gap: 8, flexGrow: 1 },
  bubble: { maxWidth: '85%', padding: 12, borderRadius: RADIUS.md, marginVertical: 3 },
  bubbleUser: { backgroundColor: COLORS.accent, alignSelf: 'flex-end' },
  bubbleIA: { backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border, alignSelf: 'flex-start' },
  bubbleText: { color: COLORS.text, fontSize: 15, lineHeight: 22 },
  bubbleTextUser: { color: '#fff' },
  thinkText: { color: COLORS.muted, fontSize: 12, fontStyle: 'italic', marginBottom: 6, lineHeight: 16 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 100 },
  emptyEmoji: { fontSize: 36, color: COLORS.accent, marginBottom: 12 },
  emptyTitle: { fontSize: 22, fontWeight: '700', color: COLORS.text, marginBottom: 4 },
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
