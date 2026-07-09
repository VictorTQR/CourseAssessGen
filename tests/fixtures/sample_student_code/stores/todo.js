import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTodoStore = defineStore('todo', () => {
  const todos = ref([])
  const remaining = computed(() => todos.value.filter(t => !t.done).length)

  function add(text) {
    todos.value.push({ id: Date.now(), text, done: false })
  }
  function toggle(id) {
    const todo = todos.value.find(t => t.id === id)
    if (todo) todo.done = !todo.done
  }
  function remove(id) {
    todos.value = todos.value.filter(t => t.id !== id)
  }

  return { todos, remaining, add, toggle, remove }
})
