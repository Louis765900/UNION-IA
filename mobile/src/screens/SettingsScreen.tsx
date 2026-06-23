import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  ScrollView, Alert, Switch, SafeAreaView,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiGet, login, logout } from '../api/client';
import { COLORS, RADIUS } from '../theme';

export default function SettingsScreen() {
  const [serverUrl, setServerUrl] = useState('http://127.0.0.1:5000');
  const [email, setEmail] = useState('');
  const [mdp, setMdp] = useState('');
  const [user, setUser] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    charger();
  }, []);

  async function charger() {
    const url = await AsyncStorage.getItem('server_url');
    if (url) setServerUrl(url);
    try {
      const me = await apiGet('/api/auth/me');
      if (me.authentifie) setUser(me.user);
    } catch {}
    try {
      const s = await apiGet('/api/status');
      setStatus(s);
    } catch {}
  }

  async function sauverUrl() {
    await AsyncStorage.setItem('server_url', serverUrl.trim());
    affMsg('URL sauvegardée !');
    charger();
  }

  async function seConnecter() {
    const r = await login(email, mdp);
    if (r.success) { setUser(r.user); setEmail(''); setMdp(''); affMsg('Connecté !'); }
    else affMsg(r.error || 'Erreur de connexion');
  }

  async function seDeconnecter() {
    await logout();
    setUser(null);
    affMsg('Déconnecté');
  }

  function affMsg(texte: string) {
    setMsg(texte);
    setTimeout(() => setMsg(''), 3000);
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.titre}>Paramètres</Text>

        {msg ? <View style={styles.msgBox}><Text style={styles.msgTxt}>{msg}</Text></View> : null}

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Serveur UNION IA</Text>
          <TextInput
            style={styles.input}
            value={serverUrl}
            onChangeText={setServerUrl}
            placeholder="http://127.0.0.1:5000"
            placeholderTextColor={COLORS.muted}
            autoCapitalize="none"
            keyboardType="url"
          />
          <TouchableOpacity style={styles.btn} onPress={sauverUrl}>
            <Text style={styles.btnTxt}>Sauvegarder</Text>
          </TouchableOpacity>
          {status && (
            <Text style={styles.info}>
              Moteur : {status.modele || '—'} | Mode : {status.mode_label || '—'}
            </Text>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>Compte</Text>
          {user ? (
            <>
              <Text style={styles.info}>Connecté en tant que <Text style={styles.accent}>{user.email}</Text></Text>
              {user.role === 'admin' && <Text style={styles.badge}>Administrateur</Text>}
              <TouchableOpacity style={[styles.btn, styles.btnDanger]} onPress={seDeconnecter}>
                <Text style={styles.btnTxt}>Se déconnecter</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <TextInput style={styles.input} value={email} onChangeText={setEmail}
                placeholder="Email" placeholderTextColor={COLORS.muted}
                keyboardType="email-address" autoCapitalize="none" />
              <TextInput style={styles.input} value={mdp} onChangeText={setMdp}
                placeholder="Mot de passe" placeholderTextColor={COLORS.muted}
                secureTextEntry />
              <TouchableOpacity style={styles.btn} onPress={seConnecter}>
                <Text style={styles.btnTxt}>Se connecter</Text>
              </TouchableOpacity>
            </>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>À propos</Text>
          <Text style={styles.info}>UNION IA Mobile v1.0.0</Text>
          <Text style={styles.info}>Assistant IA personnel propulsé par les meilleurs modèles cloud.</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: COLORS.bg },
  scroll: { padding: 16, gap: 12 },
  titre: { fontSize: 22, fontWeight: '700', color: COLORS.text, marginBottom: 8 },
  card: {
    backgroundColor: COLORS.surface, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: RADIUS.lg, padding: 16, gap: 10,
  },
  cardTitle: { fontSize: 14, fontWeight: '600', color: COLORS.muted, textTransform: 'uppercase', letterSpacing: 1 },
  input: {
    backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.border,
    borderRadius: RADIUS.md, padding: 10, color: COLORS.text, fontSize: 15,
  },
  btn: { backgroundColor: COLORS.accent, borderRadius: RADIUS.md, padding: 12, alignItems: 'center' },
  btnDanger: { backgroundColor: '#c44' },
  btnTxt: { color: '#fff', fontWeight: '600', fontSize: 15 },
  info: { color: COLORS.muted, fontSize: 14, lineHeight: 20 },
  accent: { color: COLORS.accent, fontWeight: '600' },
  badge: {
    backgroundColor: 'rgba(124,111,247,.15)', color: COLORS.accent,
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, fontSize: 12, fontWeight: '600',
    alignSelf: 'flex-start',
  },
  msgBox: {
    backgroundColor: 'rgba(68,204,153,.12)', borderWidth: 1, borderColor: 'rgba(68,204,153,.3)',
    borderRadius: RADIUS.md, padding: 10,
  },
  msgTxt: { color: '#4c9', fontSize: 14 },
});
