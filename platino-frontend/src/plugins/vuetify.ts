/**
 * plugins/vuetify.ts
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import "@mdi/font/css/materialdesignicons.css";
import { VFileUpload } from "vuetify/labs/VFileUpload";
import "vuetify/styles";

// Composables
import { createVuetify } from "vuetify";

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
  theme: {
    defaultTheme: "light",
    themes: {
      light: {
        dark: false,
        colors: {
          background: "#F3F4F6", // gris claro, lectura
          primary: "#35364aff",
        },
      },
      dark: {
        dark: true,
        colors: {
          background: "#0c0909ff", // casi negro, matiz frío
          primary: "#046865",
        },
      },
    },
  },
  components: {
    VFileUpload,
  },
});
