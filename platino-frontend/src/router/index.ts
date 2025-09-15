/**
 * router/index.ts
 *
 * Automatic routes for `./src/pages/*.vue`
 */

// Composables
import type { RouteRecordRaw } from "vue-router";
import home from "@/pages/index.vue";
import { createRouter, createWebHistory } from "vue-router/auto";
import { setupLayouts } from "virtual:generated-layouts";
// import { routes } from 'vue-router/auto-routes'
const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "home",
    component: home,
  },
  {
    path: "/dashboard",
    name: "dashboard",
    component: () => import("@/pages/dashboard/index.vue"),
    children: [
      {
        path: "chat",
        name: "chat",
        component: () => import("@/pages/dashboard/chat.vue"),
      },
      {
        path: "files",
        name: "files",
        component: () => import("@/pages/dashboard/files.vue"),
      },
    ],
  },
  {
    path: "/metrics",
    name: "metrics",
    component: () => import("@/pages/metrics/index.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: setupLayouts(routes),
});

// Simple auth guard example
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem("auth")) {
    return { path: "/" };
  }
});

// Workaround for https://github.com/vitejs/vite/issues/11804
router.onError((err, to) => {
  if (err?.message?.includes?.("Failed to fetch dynamically imported module")) {
    if (localStorage.getItem("vuetify:dynamic-reload")) {
      console.error("Dynamic import error, reloading page did not fix it", err);
    } else {
      console.log("Reloading page to fix dynamic import error");
      localStorage.setItem("vuetify:dynamic-reload", "true");
      location.assign(to.fullPath);
    }
  } else {
    console.error(err);
  }
});

router.isReady().then(() => {
  localStorage.removeItem("vuetify:dynamic-reload");
});

export default router;
