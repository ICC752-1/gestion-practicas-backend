# Development Standards - Backend

---

## 1. Nomenclatura de Ramas para Desarrollo

El proyecto adopta una estrategia basada en **GitFlow simplificado**, la cual permite estructurar el desarrollo mediante ramas claramente definidas.

### 1.1 Ramas principales

- **main**: contiene versiones estables del sistema, listas para su despliegue en producción.  
- **develop**: corresponde a la rama de integración continua, donde se consolidan los avances del desarrollo.

### 1.2 Ramas de trabajo

Todas las ramas de trabajo deben originarse desde la rama `develop` y seguir una nomenclatura estandarizada:

*\<tipo\>/\<descripcion-corta\>*

Los tipos de ramas definidos son:

- **feature/**: implementación de nuevas funcionalidades.  
- **fix/**: corrección de errores detectados durante el desarrollo.  
- **hotfix/**: solución de errores críticos en producción.  
- **refactor/**: mejoras internas sin modificar el comportamiento funcional.  
- **docs/**: cambios en documentación.  
- **test/**: desarrollo o modificación de pruebas.

Esta convención permite identificar rápidamente el propósito de cada rama, facilitando la gestión del repositorio.

---

## 2. Convención de Commits

Para mantener un historial claro y estructurado, se utilizará el estándar **Conventional Commits**.

### 2.1 Estructura del commit

*\<tipo\>(alcance): \<descripción breve\>* 

  *\[linea en blanco\]*

  *\- [cuerpo opcional pero recomendado\]*

### 2.2 Lineamientos

Los mensajes deben redactarse en **español**, además, deben contar con una descripción breve, clara y representativa del cambio realizado. El cuerpo del mensaje es opcional, pero recomendado para detallar la implementación.

### 2.3 Tipos de commits

- **feat**: nueva funcionalidad  
- **fix**: corrección de errores  
- **docs**: documentación  
- **style**: cambios de formato  
- **refactor**: mejora interna del código  
- **test**: pruebas  
- **chore**: tareas de mantenimiento

### 2.4 Trazabilidad

Se establecen las siguientes reglas:

* No eliminar commits del historial compartido.  
* No utilizar `git push --force` en ramas compartidas.  
* No reescribir historial de funcionalidades ya integradas.

Estas medidas aseguran la integridad y auditabilidad del proyecto.

---

## 3. Reglas de Integración (Pull Requests)

La integración de cambios se realizará exclusivamente mediante **Pull Requests (PR)**.

### 3.1 Flujo de integración

1. Crear rama desde `develop`.  
2. Implementar cambios.  
3. Realizar commits siguiendo la convención establecida.  
4. Publicar la rama en el repositorio remoto.  
5. Crear Pull Request hacia `develop`.

### 3.2 Normativas

1. No se permiten commits directos a `main` ni `develop`.  
2. Todo cambio debe ser revisado antes de su integración.  
3. Cada PR debe estar asociado a una tarea o requerimiento.

### 3.3 Verificaciones obligatorias

Antes de aprobar un PR, se debe asegurar que:

* El código se compila correctamente.  
* No se afectan funcionalidades existentes.  
* Se cumplen los estándares definidos.  
* El cambio ha sido probado.

---

## 4. Política de Liberación, Entregas y Versionado

El control de versiones se realizará mediante **Semantic Versioning (SemVer)**.

### 4.1 Formato de versiones

MAJOR.MINOR.PATCH

Interpretación:

* **MAJOR**: cambios incompatibles.  
* **MINOR**: nuevas funcionalidades compatibles.  
* **PATCH**: correcciones de errores.

### 4.2 Estrategia del proyecto

* **v0.1.0**: prototipo inicial.  
* **v0.5.0**: producto mínimo viable (MVP).  
* **v1.0.0**: versión estable.

### 4.3 Releases

* Cada versión liberada debe incluir:  
* Funcionalidades incorporadas.  
* Correcciones realizadas.  
* Cambios relevantes documentados en un **changelog**.  
* Las versiones oficiales se generarán desde la rama `main`.

---

## 5. Estándares de Codificación

### 5.1 Idioma

* Código fuente: **inglés**. Esto incluye carpetas, módulos, archivos, clases, funciones, variables, endpoints internos y nombres de pruebas.  
* Comentarios: **español**, solo cuando agreguen contexto útil que el código no exprese por sí mismo.  
* Documentación: **español o inglés**

### 5.2 Convenciones de nombres para Python/FastAPI

* Paquetes, carpetas y archivos Python: **snake_case** en inglés. Ejemplo: `internships`, `user_repository.py`, `auth_controller.py`.
* Variables y funciones: **snake_case** en inglés. Ejemplo: `current_user`, `create_access_token`.
* Clases: **PascalCase** en inglés. Ejemplo: `AuthService`, `InternshipRepository`.
* Constantes: **UPPER_CASE** en inglés. Ejemplo: `ACCESS_TOKEN_EXPIRE_MINUTES`.
* Rutas de API: minúsculas, plurales y en inglés cuando representen recursos. Ejemplo: `/internships`, `/documents/types`.
* Tablas y modelos ORM: nombres en inglés, alineados con el esquema relacional vigente cuando sea posible.

### 5.3 Buenas prácticas

* Desarrollar funciones pequeñas y cohesivas.  
* Utilizar nombres descriptivos.  
* Evitar duplicación de código.  
* Aplicar separación por capas:  
  * controllers  
  * services  
  * models
  * schemas
  * repositories

Estas prácticas favorecen la mantenibilidad, escalabilidad y claridad del sistema.
