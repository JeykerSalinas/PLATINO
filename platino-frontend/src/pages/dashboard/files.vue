<template>
  <v-container fluid>
    <v-row>
      <!-- <v-col cols="12">
        <v-card class="pa-4" @dragover.prevent @drop.prevent="onDrop">
          <h3 class="text-h6 mb-4">
            Arrastra archivos aquí o haz click para subir
          </h3>
          <v-file-input
            label="Sube un archivo"
            @update:modelValue="handleFileUpload"
            prepend-icon="mdi-upload"
            show-size
          />

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
                  :src="`http://localhost:8000/${doc.thumbnail}`"
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
      </v-col> -->
    </v-row>
    <!-- <v-row>
      <v-col cols="12">
        <v-select
          label="Asignar a temario"
          :items="topicsList"
          item-title="title"
          item-value="id"
          v-model="selectedTopicId"
          clearable
          class="mb-4"
        />
      </v-col>
      <v-btn icon="mdi-plus" class="ml-2" size="small" @click="addModule" />
    </v-row> -->
    <v-row class="mb-3" v-for="mod in modules" :key="mod.id">
      <v-col cols="12" class="bg-blue-grey-darken-4 rounded">
        <div class="d-flex align-center">
          <v-text-field
            v-model="mod.title"
            @input="editModule(mod)"
          ></v-text-field>
          <v-menu>
            <template v-slot:activator="{ props }">
              <v-btn
                icon="mdi-dots-horizontal"
                variant="text"
                v-bind="props"
              ></v-btn>
            </template>

            <v-list>
              <v-list-item @click="addTopic(mod)">
                <v-list-item-title
                  >Agregar Tema <v-icon>mdi-plus</v-icon></v-list-item-title
                >
              </v-list-item>
              <v-list-item @click="removeModule(mod)">
                <v-list-item-title
                  >Eliminar Módulo
                  <v-icon>mdi-delete</v-icon>
                </v-list-item-title>
              </v-list-item>
            </v-list>
          </v-menu>
        </div>
        <v-expansion-panels class="my-4">
          <v-expansion-panel class="" v-for="topic in mod.topics" :key="topic.id">
            <template #title>
              <div class="d-flex align-center justify-between w-100">
                <span>{{ topic.title }}</span>
                <div>
                  <v-btn
                    icon="mdi-pencil"
                    size="small"
                    @click.stop="editTopic(topic)"
                  />
                  <v-btn
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
                  md="2"
                  v-for="doc in documents.filter(
                    (d) => d.topic_id === topic.id
                  )"
                  :key="doc.id"
                >
                  <v-card>
                    <v-img
                      :src="`http://localhost:8000/${doc.thumbnail}`"
                      height="120"
                    />
                    <v-card-title class="text-wrap">{{
                      doc.filename
                    }}</v-card-title>
                  </v-card>
                </v-col>
              </v-row>
            </template>
          </v-expansion-panel>
        </v-expansion-panels>
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
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from "vue";
import axios from "axios";

interface Doc {
  id: number;
  filename: string;
  thumbnail: string | null;
  topic_id: number | null;
}

const documents = ref<Doc[]>([]);
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

function loadFiles() {
  axios.get("http://localhost:8000/api/files").then((res) => {
    documents.value = res.data.files;
  });
}

function loadModules() {
  axios.get("http://localhost:8000/api/modules").then((res) => {
    modules.value = res.data.modules.map((m: any) => ({ ...m, topics: [] }));
    modules.value.forEach((m) => {
      axios
        .get(`http://localhost:8000/api/modules/${m.id}/topics`)
        .then((r) => {
          const mod = modules.value.find((mm) => mm.id === m.id);
          if (mod) mod.topics = r.data.topics;
        });
    });
  });
}

function upload(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  axios
    .post("http://localhost:8000/api/files", formData, {
      params: { topic_id: selectedTopicId.value },
    })
    .then((res) => {
      documents.value.push(res.data);
    });
}

function remove(id: number) {
  axios.delete(`http://localhost:8000/api/files/${id}`).then(() => {
    documents.value = documents.value.filter((d) => d.id !== id);
  });
}

function addModule() {
  const title = prompt("Nombre del módulo");
  if (!title) return;
  axios
    .post("http://localhost:8000/api/modules", null, { params: { title } })
    .then((res) => {
      modules.value.push({ ...res.data, topics: [] });
    });
}

function addTopic(module: Module) {
  const title = prompt("Nombre del temario");
  if (!title) return;
  axios
    .post(`http://localhost:8000/api/modules/${module.id}/topics`, null, {
      params: { title },
    })
    .then((res) => {
      module.topics.push(res.data);
    });
}

function editModule(module: Module) {
  // const title = prompt("Nuevo título", module.title);

  if (!module.title) return;
  axios
    .put(`http://localhost:8000/api/modules/${module.id}`, null, {
      params: { title: module.title },
    })
    .then((res) => {
      // module.title = res.data.title;
    });
}

function editTopic(topic: Topic) {
  const title = prompt("Nuevo título", topic.title);
  if (!title || title === topic.title) return;
  axios
    .put(`http://localhost:8000/api/topics/${topic.id}`, null, {
      params: { title },
    })
    .then((res) => {
      topic.title = res.data.title;
    });
}

function removeModule(module: Module) {
  if (!confirm("¿Eliminar módulo y sus temarios?")) return;
  axios.delete(`http://localhost:8000/api/modules/${module.id}`).then(() => {
    modules.value = modules.value.filter((m) => m.id !== module.id);
    const topicIds = module.topics.map((t) => t.id);
    documents.value = documents.value.filter(
      (d) => !topicIds.includes(d.topic_id ?? -1)
    );
  });
}

function removeTopic(module: Module, topic: Topic) {
  if (!confirm("¿Eliminar temario?")) return;
  axios.delete(`http://localhost:8000/api/topics/${topic.id}`).then(() => {
    module.topics = module.topics.filter((t) => t.id !== topic.id);
    documents.value = documents.value.filter((d) => d.topic_id !== topic.id);
  });
}

function rename(doc: Doc) {
  const newName = prompt("Nuevo nombre", doc.filename);
  if (!newName || newName === doc.filename) return;
  axios
    .put(`http://localhost:8000/api/files/${doc.id}`, null, {
      params: { new_name: newName },
    })
    .then((res) => {
      doc.filename = res.data.filename;
    });
}

function handleFileUpload(newFile: File | File[]) {
  if (!newFile) return;
  const selected = Array.isArray(newFile) ? newFile[0] : newFile;
  upload(selected);
}

function onDrop(e: DragEvent) {
  const files = e.dataTransfer?.files;
  if (files && files.length) {
    upload(files[0]);
  }
}

onMounted(() => {
  loadFiles();
  loadModules();
});
</script>
