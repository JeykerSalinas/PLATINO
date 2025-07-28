<template>
  <v-container>
    <!-- <v-row>
      <v-col cols="12">
        <v-card class="pa-4" @dragover.prevent @drop.prevent="onDrop">
          <v-row class="mt-4" v-if="documents.length">
            <v-col
              cols="12"
              sm="6"
              md="3"
              v-for="doc in documents"
              :key="doc.id"
            >
              <v-card>
                <v-img
                  :src="`${doc.thumbnail}`"
                  height="120"
                  cover
                />
                <v-card-title class="text-wrap">{{
                  doc.filename
                }}</v-card-title>
                <v-card-actions>
                  <v-btn icon="mdi-pencil" @click="rename(doc)" size="small" />
                  <v-btn
                    icon="mdi-delete"
                    @click="remove(doc.id)"
                    size="small"
                  />
                </v-card-actions>
              </v-card>
            </v-col>
          </v-row>
          <div v-else class="text-medium-emphasis">No hay archivos aún</div>
        </v-card>
      </v-col>
    </v-row> -->

    <v-row v-for="mod in modules" :key="mod.id">
      <v-col cols="12">
        <div class="d-flex justify-space-between align-center">
          <div class="text-h6 px-5">
            {{ mod.title }}
          </div>
          <v-menu>
            <template v-slot:activator="{ props }">
              <v-btn
                icon="mdi-dots-vertical"
                variant="text"
                v-bind="props"
              ></v-btn>
            </template>

            <v-list>
              <v-list-item @click="addTopic(mod)">
                <v-list-item-title> Agregar Tema </v-list-item-title>
                <template v-slot:prepend>
                  <v-icon icon="mdi-plus"></v-icon>
                </template>
              </v-list-item>
              <v-list-item @click="editModule(mod)">
                <v-list-item-title> Editar nombre </v-list-item-title>
                <template v-slot:prepend>
                  <v-icon icon="mdi-pencil"></v-icon>
                </template>
              </v-list-item>
              <v-list-item @click="removeModule(mod)">
                <template v-slot:prepend>
                  <v-icon icon="mdi-delete"></v-icon>
                </template>
                <v-list-item-title>Eliminar Módulo </v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </div>
        <v-divider></v-divider>
        <v-expansion-panels size="sm" class="my-4" v-if="mod.topics.length">
          <v-expansion-panel
            class=""
            v-for="topic in mod.topics"
            :key="topic.id"
          >
            <template #title>
              <div class="d-flex align-center justify-space-between w-100">
                <div>{{ topic.title }}</div>
                <div class="d-flex align-center">
                  <v-btn
                    density="compact"
                    variant="plain"
                    icon="mdi-pencil"
                    size="small"
                    @click.stop="editTopic(topic)"
                  />
                  <v-btn
                    density="compact"
                    variant="plain"
                    icon="mdi-delete"
                    size="small"
                    class="ml-2"
                    @click.stop="removeTopic(mod, topic)"
                  />
                </div>
              </div>
            </template>
            <template #text>
              <v-row>
                <v-col
                  cols="12"
                  sm="6"
                  v-for="doc in documents.filter(
                    (d) => d.topic_id === topic.id
                  )"
                  :key="doc.id"
                >
                  <div
                    class="border rounded d-flex cursor-pointer position-relative"
                    @click="viewDocument(doc)"
                  >
                    <div class="border-e">
                      <template v-if="doc.thumbnail">
                        <v-img
                          height="90"
                          width="120"
                          cover
                          :src="`${apiUrl}${doc.thumbnail}`"
                        />
                      </template>
                      <template v-else>
                        <div
                          class="d-flex align-center justify-center"
                          style="height: 90px; width: 120px"
                        >
                          <v-icon size="64">mdi-file-word</v-icon>
                        </div>
                      </template>
                    </div>
                    <div class="d-flex align-center pa-3 overflow-hidden">
                      <div class="pb-3 me-5 text-truncate">
                        {{ doc.filename }}
                      </div>
                    </div>
                    <v-btn
                      density="compact"
                      variant="plain"
                      icon="mdi-close"
                      size="small"
                      class="ml-2 position-absolute bottom-0 right-0 top-0 pa-2 pe-3"
                      @click.stop="remove(doc.id)"
                    />
                  </div>
                </v-col>
                <v-col cols="12" sm="6" v-if="loadingFile">
                  <div
                    class="border rounded d-flex cursor-pointer align-center justify-center position-relative"
                    style="height: 90px"
                  >
                    <v-progress-circular
                      :size="50"
                      color="primary"
                      indeterminate
                    ></v-progress-circular></div
                ></v-col>
                <v-col cols="12" sm="6"
                  ><v-file-upload
                    density="compact"
                    title="Arrastra o agrega archivos"
                    style="min-height: 90px"
                    @update:modelValue="handleFileUpload($event, topic.id)"
                    :disabled="loadingFile"
                  ></v-file-upload>
                </v-col>
              </v-row>
            </template>
          </v-expansion-panel>
        </v-expansion-panels>
        <div class="px-5 py-3 text-caption" v-else>
          No existen temas para el módulo: "{{ mod.title }}"
        </div>
      </v-col>
    </v-row>
    <v-row>
      <v-col cols="12 text-end">
        <v-btn color="primary" @click="addModule"
          ><v-icon>mdi-plus</v-icon> Agregar Módulo
        </v-btn>
      </v-col>
    </v-row>
  </v-container>

  <v-dialog v-model="dialog" max-width="1200">
    <v-card v-if="selectedDoc">
      <v-card-title class="d-flex justify-space-between">
        {{ selectedDoc.filename }}
        <div>
          <v-btn
            density="compact"
            variant="plain"
            size="small"
            icon="mdi-download"
            :href="`${selectedDoc.filepath}`"
            download
          />
          <v-btn
            density="compact"
            variant="plain"
            icon="mdi-delete"
            size="small"
            @click.stop="remove(selectedDoc.id)"
          />
          <v-btn
            density="compact"
            variant="plain"
            size="small"
            icon="mdi-close"
            @click="dialog = false"
          />
        </div>
      </v-card-title>
      <v-card-text>
        <v-row>
          <v-col cols="12" sm="6">
            <iframe
              v-if="isPdf(selectedDoc.filename)"
              :src="`${apiUrl}${selectedDoc.filepath}`"
              style="width: 100%; height: 75vh"
            ></iframe>
            <div
              v-else
              class="d-flex align-center justify-center"
              style="height: 75vh"
            >
              <v-icon size="64">mdi-file-word</v-icon>
            </div>
          </v-col>
          <v-col cols="12" sm="6" style="max-height: 75vh; overflow-y: auto">
            <v-list>
              <v-list-item
                v-for="(chunk, idx) in selectedDoc.chunks"
                :key="idx"
              >
                <v-list-item-subtitle>{{ chunk }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import axios from "@/plugins/axios";

interface Doc {
  id: number;
  filename: string;
  thumbnail: string | null;
  topic_id: number | null;
}

interface DocDetail extends Doc {
  filepath: string;
  metadata: any;
  chunks: string[];
}
const apiUrl = import.meta.env.VITE_API_URL;
const documents = ref<Doc[]>([]);
const selectedDoc = ref<DocDetail | null>(null);
const dialog = ref(false);
function isPdf(name: string) {
  return name.toLowerCase().endsWith(".pdf");
}
interface Topic {
  id: number;
  title: string;
  module_id: number;
}
interface Module {
  id: number;
  title: string;
  topics: Topic[];
  edit: boolean;
}

const modules = ref<Module[]>([]);
const selectedTopicId = ref<number | null>(null);
const topicsList = computed(() => modules.value.flatMap((m) => m.topics));
const fileInput = ref<HTMLInputElement | null>(null);
const loadingFile = ref(false);
function loadFiles() {
  axios.get("api/files").then((res) => {
    documents.value = res.data.files;
  });
}

function loadModules() {
  axios.get("api/modules").then((res) => {
    modules.value = res.data.modules.map((m: any) => ({ ...m, topics: [] }));
    modules.value.forEach((m) => {
      axios.get(`api/modules/${m.id}/topics`).then((r) => {
        const mod = modules.value.find((mm) => mm.id === m.id);
        if (mod) mod.topics = r.data.topics;
      });
    });
  });
}

function upload(file: File, topicId: number) {
  const formData = new FormData();
  formData.append("file", file);
  loadingFile.value = true;
  axios
    .post("api/files", formData, {
      params: { topic_id: topicId },
    })
    .then((res) => {
      documents.value.push(res.data);
    })
    .finally(() => {
      loadingFile.value = false;
    });
}

function remove(id: number) {
  if (!confirm("¿Eliminar documento?")) return;
  axios.delete(`api/files/${id}`).then(() => {
    documents.value = documents.value.filter((d) => d.id !== id);
  });
}

function addModule() {
  const title = prompt("Nombre del módulo");
  if (!title) return;
  axios.post("api/modules", null, { params: { title } }).then((res) => {
    modules.value.push({ ...res.data, topics: [] });
  });
}

function addTopic(module: Module) {
  const title = prompt("Nombre del temario");
  if (!title) return;
  axios
    .post(`api/modules/${module.id}/topics`, null, {
      params: { title },
    })
    .then((res) => {
      module.topics.push(res.data);
    });
}

function editModule(module: Module) {
  const title = prompt("Nuevo título", module.title);
  if (!module.title) return;
  axios
    .put(`api/modules/${module.id}`, null, {
      params: { title: title },
    })
    .then((res) => {
      module.title = res.data.title;
    });
}

function editTopic(topic: Topic) {
  const title = prompt("Nuevo título", topic.title);
  if (!title || title === topic.title) return;
  axios
    .put(`api/topics/${topic.id}`, null, {
      params: { title },
    })
    .then((res) => {
      topic.title = res.data.title;
    });
}

function removeModule(module: Module) {
  if (!confirm("¿Eliminar módulo y sus temarios?")) return;
  axios.delete(`api/modules/${module.id}`).then(() => {
    modules.value = modules.value.filter((m) => m.id !== module.id);
    const topicIds = module.topics.map((t) => t.id);
    documents.value = documents.value.filter(
      (d) => !topicIds.includes(d.topic_id ?? -1)
    );
  });
}

function removeTopic(module: Module, topic: Topic) {
  if (!confirm("¿Eliminar temario?")) return;
  axios.delete(`api/topics/${topic.id}`).then(() => {
    module.topics = module.topics.filter((t) => t.id !== topic.id);
    documents.value = documents.value.filter((d) => d.topic_id !== topic.id);
  });
}

function viewDocument(doc: Doc) {
  axios.get(`api/files/${doc.id}`).then((res) => {
    selectedDoc.value = res.data;
    dialog.value = true;
  });
}

function rename(doc: Doc) {
  const newName = prompt("Nuevo nombre", doc.filename);
  if (!newName || newName === doc.filename) return;
  axios
    .put(`api/files/${doc.id}`, null, {
      params: { new_name: newName },
    })
    .then((res) => {
      doc.filename = res.data.filename;
    });
}

function handleFileUpload(newFile: File | File[], topicId: number) {
  if (!newFile) return;
  console.log(newFile);
  const selected = Array.isArray(newFile) ? newFile[0] : newFile;
  upload(selected, topicId);
}

function onDrop(e: DragEvent, topicId: number) {
  const files = e.dataTransfer?.files;
  if (files && files.length) {
    upload(files[0], topicId);
  }
}
const triggerFileInput = () => {
  fileInput.value?.click();
};

const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  if (file) {
    // Puedes subirlo a tu backend aquí o emitirlo al componente padre
    console.log("Archivo seleccionado:", file.name);
  }
};
onMounted(() => {
  loadFiles();
  loadModules();
});
</script>
<style lang="scss">
.v-file-upload {
  max-height: 80px !important;
  .v-file-upload-title {
    font-size: small;
    font-weight: 400;
  }
}
.v-file-upload-items {
  display: none !important;
}
</style>
