<template>
  <v-app-bar title="PLATINO" density="compact">
    <template v-slot:prepend>
      <v-app-bar-nav-icon
        @click="currentDrawer = !currentDrawer"
      ></v-app-bar-nav-icon>
    </template>

    <v-btn icon @click="toggleTheme" size="small">
      <v-icon>mdi-theme-light-dark</v-icon>
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
import { useTheme } from "vuetify";

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
const theme = useTheme();
function toggleTheme() {
  theme.global.name.value =
    theme.global.name.value === "dark" ? "light" : "dark";
  localStorage.setItem("platino-theme", theme.global.name.value);
}
</script>
