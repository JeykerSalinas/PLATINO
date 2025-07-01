<template>
  <v-app-bar title="PLATINO">
    <template v-slot:prepend>
      <v-app-bar-nav-icon
        @click="currentDrawer = !currentDrawer"
      ></v-app-bar-nav-icon>
    </template>
    <v-btn icon>
      <v-icon>mdi-magnify</v-icon>
    </v-btn>

    <v-btn icon>
      <v-icon>mdi-dots-vertical</v-icon>
    </v-btn>
  </v-app-bar>

  <v-navigation-drawer v-model="currentDrawer">
    <v-list nav>
      <v-list-item
        v-for="item in drawerItems"
        :key="item.title"
        :title="item.title"
        :to="item.to"
      >
        <template v-slot:prepend>
          <v-icon :icon="item.icon"></v-icon>
        </template>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>

  <router-view />
</template>

<script setup lang="ts">
import { ref } from "vue";

const drawerItems = ref([
  {
    title: "Home",
    to: "/",
    icon: "mdi-home",
  },
  {
    title: "Chat",
    to: "/dashboard/chat",
    icon: "mdi-chat",
  },
  {
    title: "Documentos",
    to: "/dashboard/files",
    icon: "mdi-folder",
  },
]);
const currentDrawer = ref(false);
</script>
