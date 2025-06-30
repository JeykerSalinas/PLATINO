<template>
  <v-container fluid>
    <v-row>
      <v-col cols="12">
        <v-card class="pa-4" @dragover.prevent @drop.prevent="onDrop">
          <h3 class="text-h6 mb-4">Arrastra archivos aquí o haz click para subir</h3>
          <v-file-input label="Selecciona archivo" @change="handleFileUpload" />

          <v-row class="mt-4" v-if="documents.length">
            <v-col cols="12" sm="6" md="3" v-for="doc in documents" :key="doc.id">
              <v-card>
                <v-img :src="doc.thumbnail" height="120" cover />
                <v-card-title class="text-wrap">{{ doc.filename }}</v-card-title>
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
import { ref, onMounted } from 'vue'
import axios from 'axios'

interface Doc {
  id: number
  filename: string
  thumbnail: string | null
}

const documents = ref<Doc[]>([])

function loadFiles() {
  axios.get('http://localhost:8000/api/files').then((res) => {
    documents.value = res.data.files
  })
}

function upload(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  axios.post('http://localhost:8000/api/files', formData).then((res) => {
    documents.value.push(res.data)
  })
}

function handleFileUpload(newFile: File | File[]) {
  if (!newFile) return
  const selected = Array.isArray(newFile) ? newFile : [newFile]
  upload(selected[0])
}

function onDrop(e: DragEvent) {
  const files = e.dataTransfer?.files
  if (files && files.length) {
    upload(files[0])
  }
}

onMounted(loadFiles)
</script>
