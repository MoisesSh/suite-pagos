// ===========================
// REGEX GLOBALES REUTILIZABLES
// ===========================
// Cada regex tiene su mensaje de error asociado.
// Usar en schemas Zod (modules/*/ui/schema/) — nunca hardcodear regex inline.

/** Dominio FQDN: labels alfanuméricos con guiones internos, TLD de 2+ letras */
export const DOMAIN =
  /^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*\.[a-zA-Z]{2,}$/;
export const DOMAIN_MSG = "Dominio inválido. Ejemplo: conatel-en-linea.gob.ve";

/** Nombre de aplicación: letras, números, espacios y guiones, 2 a 100 caracteres */
export const APP_NAME = /^[a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ\s-]{2,100}$/;
export const APP_NAME_MSG = "Solo letras, números, espacios y guiones (2 a 100 caracteres)";
