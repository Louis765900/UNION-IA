import React, { useState, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  SafeAreaView, RefreshControl,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { apiGet, apiPost } from '../api/client';
import { COLORS, RADIUS } from '../theme';

interface Conv {
  id: number;
  titre: string;
  nb: number;
  maj_le: number;
}

interface Props {
  onSelect: (id: number) => void;
}

export default function ConversationsScreen({ onSelect }: Props) {
  const [convs, setConvs] = useState<Conv[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const charger = useCallback(async () => {
    try {
      const data = await apiGet('/api/conversations');
      setConvs(data.conversations || []);
    } catch {}
  }, []);

  useFocusEffect(useCallback(() => { charger(); }, [charger]));

  async function onRefresh() {
    setRefreshing(true);
    await charger();
    setRefreshing(false);
  }

  async function nouvConv() {
    const data = await apiPost('/api/conversations', {});
    if (data.id) onSelect(data.id);
  }

  function formatDate(ts: number) {
    const d = new Date(ts * 1000);
    return d.toLocaleDateString('fr', { day: '2-digit', month: 'short' });
  }

  const renderItem = ({ item }: { item: Conv }) => (
    <TouchableOpacity style={styles.item} onPress={() => onSelect(item.id)}>
      <View style={styles.itemContent}>
        <Text style={styles.itemTitle} numberOfLines={1}>{item.titre}</Text>
        <Text style={styles.itemMeta}>{item.nb} message{item.nb > 1 ? 's' : ''} · {formatDate(item.maj_le)}</Text>
      </View>
      <Text style={styles.chevron}>›</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.titre}>Conversations</Text>
        <TouchableOpacity style={styles.btnNouvelle} onPress={nouvConv}>
          <Text style={styles.btnNouvelleTxt}>+ Nouveau</Text>
        </TouchableOpacity>
      </View>
      <FlatList
        data={convs}
        keyExtractor={c => String(c.id)}
        renderItem={renderItem}
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={COLORS.accent} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyText}>Aucune conversation pour l'instant.</Text>
            <TouchableOpacity style={styles.btnNouvelle} onPress={nouvConv}>
              <Text style={styles.btnNouvelleTxt}>Démarrer une conversation</Text>
            </TouchableOpacity>
          </View>
        }
      />
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
  titre: { fontSize: 18, fontWeight: '700', color: COLORS.text },
  list: { padding: 8 },
  item: {
    flexDirection: 'row', alignItems: 'center', backgroundColor: COLORS.surface,
    borderWidth: 1, borderColor: COLORS.border, borderRadius: RADIUS.md,
    padding: 14, marginVertical: 4,
  },
  itemContent: { flex: 1 },
  itemTitle: { fontSize: 15, fontWeight: '600', color: COLORS.text, marginBottom: 3 },
  itemMeta: { fontSize: 12, color: COLORS.muted },
  chevron: { fontSize: 20, color: COLORS.muted, marginLeft: 8 },
  btnNouvelle: {
    backgroundColor: COLORS.accent, borderRadius: RADIUS.md,
    paddingHorizontal: 14, paddingVertical: 8,
  },
  btnNouvelleTxt: { color: '#fff', fontWeight: '600', fontSize: 14 },
  empty: { alignItems: 'center', paddingTop: 80, gap: 16 },
  emptyText: { color: COLORS.muted, fontSize: 15, marginBottom: 8 },
});
