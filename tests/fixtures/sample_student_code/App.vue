<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup>
import { useTodoStore } from './stores/todo'
const todoStore = useTodoStore()
</script>
