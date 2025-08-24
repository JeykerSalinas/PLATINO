<template>
  <div
    class="container pa-3 d-flex flex-column justify-content-between fill-height"
  >
    <div class="messages-container pt-4" ref="messagesContainer">
      <div v-if="messages.length > 0" class="messages-list">
        <template v-for="(msg, index) in messages" :key="index">
          <div
            class="mb-1 d-flex"
            :class="
              msg.from === 'user'
                ? ' user-message text-end justify-end'
                : 'ia-message'
            "
          >
            <span
              v-if="msg.from === 'user'"
              class="bg-surface-light rounded-lg pa-4"
            >
              {{ msg.text }}
            </span>
            <div
              v-else
              class="markdown-body"
              v-html="renderMarkdown(msg.text)"
            ></div>
            <!-- Opcional: fuentes del RAG (si guardaste meta en el mensaje) -->
          </div>
          <v-tooltip interactive>
            <template v-slot:activator="{ props: activatorProps }">
              <v-icon-btn
                icon="mdi-information-outline"
                v-bind="activatorProps"
                v-if="msg.meta?.chunks?.length"
              ></v-icon-btn>
            </template>
            <strong>Fuentes:</strong>
            <ul class="pl-4" v-if="msg.meta?.chunks?.length">
              <li v-for="(s, i) in msg.meta.chunks" :key="i">
                {{ s.filename || "documento" }}
                <span v-if="s.topic"> — {{ s.topic }}</span>
                <span v-if="s.module"> ({{ s.module }})</span>
              </li>
            </ul>
          </v-tooltip>
        </template>
      </div>

      <div v-if="error">
        <span
          class="text-on-surface bg-red-accent-4 border border-red rounded-lg py-2 px-6 mr-3"
        >
          {{ error }}
        </span>
      </div>
    </div>
    <div class="mt-3 input-container">
      <spinner v-if="isLoading" />
      <!-- Input de PDF oculto -->
      <input
        ref="fileInput"
        accept="application/pdf"
        class="d-none"
        :disabled="isLoading"
        type="file"
        @change="handleFileChange"
      />

      <!-- Input de texto -->
      <v-text-field
        v-model="input"
        append-icon="mdi-send"
        label="Escribe tu mensaje"
        :disabled="isLoading"
        @click:append="send"
        @dragover.prevent
        @drop.prevent="onDrop"
        @keyup.enter="send"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import spinner from "@/components/ui/spinner.vue";
import axios from "@/plugins/axios";
import {
  consumeNdjsonStream,
  type MetaEvent,
  type OllamaChunk,
} from "@/utils/ndjsonStream";
import { useOllamaStore } from "@/stores/ollama";
import { renderMarkdown } from "@/utils/md";
// 👇 controlador global de cancelación
let controller: AbortController | null = null;
const messagesContainer = ref<HTMLElement | null>(null);
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
    const { data } = await axios.post("api/files_2", formData);
    if (data.chunks) {
      for (const chunk of data.chunks as string[]) {
        store.addMessage({ from: "ai", text: chunk });
      }
    }
  } catch (error_) {
    console.error("Error al dividir PDF:", error_);
  }
}
function appendToMessage(index: number, chunk: string) {
  if (!store.messages[index]) return;
  store.messages[index].text = (store.messages[index].text || "") + chunk;
}

function updateMessageMeta(index: number, meta: any) {
  if (!store.messages[index]) return;
  store.messages[index].meta = meta;
}
onMounted(async () => {
  store.connect();
});

// function send() {
//   if (!input.value) return;
//   store.sendMessage(input.value);
//   input.value = "";
// }

const OLLAMA_URL = import.meta.env.VITE_OLLAMA_URL || "http://localhost:11434";

// const _sendMesageToOllama = async (message: string) => {
//   try {
//     const response = await axios.post(`api/chat_rag`, {
//       messages: [
//         { role: "user", content: message }, // o content: [{type:"text", text:"Hola"}] según tu API
//       ],
//       stream: true,
//       question: message,
//     });
//     store.addMessage({
//       from: "ai",
//       text: response.data.answer,
//     });
//     return response.data;
//   } catch (error) {
//     console.error("Error al enviar el mensaje a Ollama:", error);
//     return null;
//   }
// };
// function send() {
//   if (!input.value) return;

//   const text = input.value;
//   input.value = "";

//   // Agregar mensaje del usuario
//   store.addMessage({
//     from: "user",
//     text,
//   });

//   // Inicializar mensaje del asistente
//   let aiResponse = "";
//   store.addMessage({
//     from: "ai",
//     text: aiResponse,
//   });

//   // Referencia al mensaje recién agregado para ir actualizándolo
//   const aiIndex = store.messages.length - 1;

//   error.value = "";
//   // sendMessageToOllamaStream(text, (chunk) => {
//   //   aiResponse += chunk;
//   //   store.messages[aiIndex].text = aiResponse;
//   // }).catch(() => {
//   //   store.messages[aiIndex].text = "";
//   // });
//   _sendMesageToOllama(text);
// }

async function send() {
  if (!input.value.trim()) return;

  // 1) Mensaje del usuario
  const userText = input.value;
  input.value = "";
  store.addMessage({ from: "user", text: userText });

  // 2) Placeholder del asistente (iremos rellenando)
  store.addMessage({ from: "ai", text: "" });
  const aiIndex = store.messages.length - 1;

  error.value = "";
  isLoading.value = true;

  // 3) Cancelación
  controller?.abort();
  controller = new AbortController();

  try {
    const res = await fetch(`http://localhost:8000/api/chat_rag`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: userText }),
      signal: controller.signal,
    });

    let finished = false;

    await consumeNdjsonStream(res, {
      onMeta(meta: MetaEvent) {
        // Guarda fuentes/meta en el mensaje IA
        if (typeof (store as any).updateMessageMeta === "function") {
          (store as any).updateMessageMeta(aiIndex, meta);
        } else {
          updateMessageMeta(aiIndex, meta);
        }
      },
      async onToken(t: string) {
        // Añade token y autoscroll
        if (typeof (store as any).appendToMessage === "function") {
          (store as any).appendToMessage(aiIndex, t);
        } else {
          appendToMessage(aiIndex, t);
        }
        await nextTick();
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop =
            messagesContainer.value.scrollHeight;
        }
      },
      onErrorLine(raw: string) {
        console.warn("Línea NDJSON no JSON:", raw);
      },
      onDone(_stats?: OllamaChunk) {
        finished = true;
      },
    });

    if (!finished) {
      console.warn("Stream finalizado sin 'done:true'");
    }
  } catch (e: any) {
    error.value =
      e?.name === "AbortError"
        ? "Petición cancelada"
        : e?.message ?? "Error de red";
  } finally {
    isLoading.value = false;
    controller = null;
  }
}

function cancel() {
  controller?.abort();
  controller = null;
  isLoading.value = false;
}

// const sendMessageToOllamaStream = async (
//   prompt: string,
//   onChunk: (text: string) => void
// ) => {
//   isLoading.value = true;
//   try {
//     const response = await fetch(`${OLLAMA_URL}/api/generate`, {
//       method: "POST",
//       headers: {
//         "Content-Type": "application/json",
//       },
//       body: JSON.stringify({
//         model: "llama3",
//         prompt,
//         stream: true,
//       }),
//     });

//     const reader = response.body?.getReader();
//     const decoder = new TextDecoder("utf8");

//     let fullText = "";

//     if (!reader) throw new Error("sin lector");

//     while (true) {
//       const { done, value } = await reader.read();
//       if (done) break;

//       const chunk = decoder.decode(value, { stream: true });

//       // Ollama envía múltiples objetos JSON por línea
//       const lines = chunk.split("\n").filter(Boolean);

//       for (const line of lines) {
//         try {
//           const json = JSON.parse(line);
//           if (json.response) {
//             fullText += json.response;
//             onChunk(json.response); // Emite fragmento
//           }
//         } catch (error_) {
//           console.error("Error al parsear línea:", line, error_);
//         }
//       }
//     }

//     return fullText;
//   } catch (error_) {
//     error.value = "Error al comunicarse con la IA";
//     throw error_;
//   } finally {
//     isLoading.value = false;
//   }
// };
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

.markdown-body {
  white-space: normal;
  line-height: 1.55;
}
.markdown-body pre {
  overflow: auto;
  padding: 12px;
  border-radius: 8px;
}
.markdown-body code {
  padding: 0 4px;
}
</style>
<route lang="yaml">
meta:
  requiresAuth: false
</route>
