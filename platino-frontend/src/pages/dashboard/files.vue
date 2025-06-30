<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
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
                <v-img :src="doc.thumbnail" height="120" cover />
                <v-card-title class="text-wrap">{{ doc.filename }}</v-card-title>
                <v-card-actions>
                  <v-btn icon="mdi-pencil" @click="rename(doc)" size="small" />
                  <v-btn icon="mdi-delete" @click="remove(doc.id)" size="small" />
                </v-card-actions>
              </v-card>
            </v-col>
          </v-row>
          <div v-else class="text-medium-emphasis">No hay archivos aún</div>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import axios from "axios";

interface Doc {
  id: number;
  filename: string;
  thumbnail: string | null;
}

const documents = ref<Doc[]>([]);

function loadFiles() {
  axios.get("http://localhost:8000/api/files").then((res) => {
    documents.value = res.data.files;
  });
}

function upload(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  axios.post("http://localhost:8000/api/files", formData).then((res) => {
    documents.value.push(res.data);
  });
}

function remove(id: number) {
  axios.delete(`http://localhost:8000/api/files/${id}`).then(() => {
    documents.value = documents.value.filter((d) => d.id !== id);
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

onMounted(loadFiles);
</script>
