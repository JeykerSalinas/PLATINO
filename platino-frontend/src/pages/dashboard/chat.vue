<template>
  <div class="pa-3 d-flex flex-column justify-end fill-height">
    <div>
      <v-list>
        <v-list-item v-for="(msg, index) in messages" :key="index">
          <v-list-item-content>
            <v-list-item-title class="text-subtitle-1">
              {{ msg.from }}
            </v-list-item-title>
            <v-list-item-subtitle>
              {{ msg.text }}
            </v-list-item-subtitle>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </div>
    <div class="mt-3">
      <!-- Input de PDF oculto -->
      <input
        ref="fileInput"
        type="file"
        accept="application/pdf"
        class="d-none"
        @change="handleFileChange"
      />

      <!-- Input de texto -->
      <v-text-field
        v-model="input"
        label="Escribe tu mensaje"
        append-icon="mdi-send"
        @click:append="send"
        @keyup.enter="send"
        @dragover.prevent
        @drop.prevent="onDrop"
      />
    </div>
    <!-- Mensajes -->
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useOllamaStore } from "@/stores/ollama";
import axios from "axios";

const store = useOllamaStore();
const input = ref("");
const messages = computed(() => store.messages);
const fileInput = ref<HTMLInputElement | null>(null);

function onDrop(e: DragEvent) {
  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    uploadPdf(files[0]);
  }
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  const files = target.files;
  if (files && files.length > 0) {
    uploadPdf(files[0]);
  }
  if (target) target.value = "";
}

async function uploadPdf(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  try {
    const { data } = await axios.post(
      "http://localhost:8000/api/files_2",
      formData
    );
    if (data.chunks) {
      data.chunks.forEach((chunk: string) => {
        store.addMessage({ from: "ai", text: chunk });
      });
    }
  } catch (err) {
    console.error("Error al dividir PDF:", err);
  }
}

onMounted(async () => {
  store.connect();
});

// function send() {
//   if (!input.value) return;
//   store.sendMessage(input.value);
//   input.value = "";
// }

const sendMesageToOllama = async (message: string) => {
  try {
    const response = await axios.post("http://localhost:11434/api/generate", {
      model: "llama3",
      prompt: message,
      stream: true,
    });
    return response.data;
  } catch (error) {
    console.error("Error al enviar el mensaje a Ollama:", error);
    return null;
  }
};
// function send() {
//   if (!input.value) return;
//   let text = input.value;
//   input.value = "";
//   store.addMessage({
//     from: "user",
//     text: text,
//   });
//   sendMesageToOllama(text).then((response) => {
//     if (response) {
//       store.addMessage({
//         from: "ai",
//         text: response.response,
//       });
//     }
//   });
// }
function send() {
  if (!input.value) return;

  const text = input.value;
  input.value = "";

  // Agregar mensaje del usuario
  store.addMessage({
    from: "user",
    text,
  });

  // Inicializar mensaje del asistente
  let aiResponse = "";
  store.addMessage({
    from: "ai",
    text: aiResponse,
  });

  // Referencia al mensaje recién agregado para ir actualizándolo
  const aiIndex = store.messages.length - 1;

  sendMessageToOllamaStream(text, (chunk) => {
    aiResponse += chunk;
    store.messages[aiIndex].text = aiResponse;
  });
}

const sendMessageToOllamaStream = async (
  prompt: string,
  onChunk: (text: string) => void
) => {
  const response = await fetch("http://localhost:11434/api/generate", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "llama3",
      prompt,
      stream: true,
    }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder("utf-8");

  let fullText = "";

  if (!reader) return;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunk = decoder.decode(value, { stream: true });

    // Ollama envía múltiples objetos JSON por línea
    const lines = chunk.split("\n").filter(Boolean);

    for (const line of lines) {
      try {
        const json = JSON.parse(line);
        if (json.response) {
          fullText += json.response;
          onChunk(json.response); // Emite fragmento
        }
      } catch (err) {
        console.error("Error al parsear línea:", line, err);
      }
    }
  }

  return fullText;
};
</script>

<route lang="yaml">
meta:
  requiresAuth: false
</route>
