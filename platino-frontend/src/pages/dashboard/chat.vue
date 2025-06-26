<template>
  <v-container>
    <h2 class="mb-4">Chat con IA</h2>
    <v-list class="mb-4">
      <v-list-item v-for="(msg, index) in messages" :key="index">
        <v-list-item-content>
          <v-list-item-title class="text-subtitle-1">
            {{ msg.from }}:
          </v-list-item-title>
          <v-list-item-subtitle>{{ msg.text }}</v-list-item-subtitle>
        </v-list-item-content>
      </v-list-item>
    </v-list>
    <v-text-field
      v-model="input"
      label="Escribe tu mensaje"
      append-icon="mdi-send"
      @click:append="send"
      @keyup.enter="send"
    />
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useOllamaStore } from "@/stores/ollama";
const store = useOllamaStore();
const input = ref("");
const messages = computed(() => store.messages);

onMounted(async () => {
  store.connect();
});

function send() {
  if (!input.value) return;
  store.sendMessage(input.value);
  input.value = "";
}
</script>

<route lang="yaml">
meta:
  requiresAuth: false
</route>
