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
import axios from "axios";
const store = useOllamaStore();
const input = ref("");
const messages = computed(() => store.messages);

onMounted(async () => {
  // store.connect();
});

const sendMesageToOllama = async (message: string) => {
  try {
    const response = await axios.post("http://localhost:11434/api/generate", {
      model: "llama3",
      prompt: message,
      stream: false,
    });
    return response.data;
  } catch (error) {
    console.error("Error al enviar el mensaje a Ollama:", error);
    return null;
  }
};
function send() {
  if (!input.value) return;
  store.addMessage({
    from: "user",
    text: input.value,
  });
  input.value = ""; // Limpiar el campo de entrada
  sendMesageToOllama(input.value).then((response) => {
    if (response) {
      store.addMessage({
        from: "ai",
        text: response.response,
      });
    }
  });
}
</script>

<route lang="yaml">
meta:
  requiresAuth: false
</route>
