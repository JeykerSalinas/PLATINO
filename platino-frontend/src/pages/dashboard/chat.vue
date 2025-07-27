<template>
  <div
    class="container pa-3 d-flex flex-column justify-content-between fill-height"
  >
    <div class="messages-container pt-4">
      <div v-if="messages.length" class="messages-list">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="mb-4"
          :class="msg.from === 'user' ? ' user-message text-end' : 'ia-message'"
        >
          <span
            :class="
              msg.from === 'user' ? 'bg-surface-light rounded-lg pa-4' : ''
            "
          >
            {{ msg.text }}
          </span>
        </div>
      </div>

      <div v-if="error" class="text-error">{{ error }}</div>
    </div>
    <div class="mt-3 input-container">
      <spinner v-if="isLoading"></spinner>
      <!-- Input de PDF oculto -->
      <input
        ref="fileInput"
        type="file"
        accept="application/pdf"
        class="d-none"
        @change="handleFileChange"
        :disabled="isLoading"
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useOllamaStore } from "@/stores/ollama";
import axios from "@/plugins/axios";

import spinner from "@/components/ui/spinner.vue";

const store = useOllamaStore();
const input = ref("");
const messages = computed(() => store.messages);
const fileInput = ref<HTMLInputElement | null>(null);
const isLoading = ref(false);
const error = ref("");

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
      "api/files_2",
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

  error.value = "";
  sendMessageToOllamaStream(text, (chunk) => {
    aiResponse += chunk;
    store.messages[aiIndex].text = aiResponse;
  }).catch(() => {
    store.messages[aiIndex].text = "";
  });
}

const sendMessageToOllamaStream = async (
  prompt: string,
  onChunk: (text: string) => void
) => {
  isLoading.value = true;
  try {
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

    if (!reader) throw new Error("sin lector");

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
  } catch (err) {
    error.value = "Error al comunicarse con la IA";
    throw err;
  } finally {
    isLoading.value = false;
  }
};
</script>
<style lang="scss" scoped>
.container {
  max-width: 1200px;
  max-height: calc(100vh - 100px);
  margin: 0 auto;
  .messages-container {
    flex: 1;
    overflow-y: auto;
  }
  .user-message {
    max-width: 66%;
    margin-left: auto;
  }
}
</style>
<route lang="yaml">
meta:
  requiresAuth: false
</route>
