<template>
  <v-layout class="rounded rounded-md border fill-height">
    <v-app-bar title="PLATINO"></v-app-bar>

    <v-navigation-drawer>
      <v-list nav>
        <v-list-item title="Navigation drawer" link></v-list-item>
      </v-list>
    </v-navigation-drawer>
    <RouterView />
  </v-layout>
</template>

<script lang="ts" setup>
import { RouterView } from "vue-router";
</script>
<style lang="scss">
#app {
  height: 100vh;
}
</style>
