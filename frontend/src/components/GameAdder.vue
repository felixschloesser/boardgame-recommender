<script lang="ts" setup>
import DropDownSearch from './DropDownSearch.vue'
import type { Option } from '../BoardGame.mjs'
import { onMounted, ref } from 'vue'

interface Props {
  options: Option[]
  id?: string // id can be undefined, get id from session if already existed
}

const props = defineProps<Props>()
const selectedGame = ref<Option | undefined>(undefined)

const addedGames = ref<Option[]>([])

onMounted(() => {
  fetchEarlierPreferences()
})

const fetchEarlierPreferences = () => {
  if (props.id) {
    // Fetch previously added games using the id prop
    // This is a placeholder for actual fetch logic
    console.log(`Fetching earlier preferences for id: ${props.id}`)
  }
}

const addGame = () => {
  if (selectedGame.value) {
    // Avoid adding duplicates
    if (!addedGames.value.find((game) => game.id === selectedGame.value?.id)) {
      addedGames.value.push(selectedGame.value)
    }
    selectedGame.value = undefined
  }
}

const removeGame = (game: Option) => {
  addedGames.value = addedGames.value.filter((g) => g.id !== game.id)
}

// Expose the getGames method to the parent
const getGames = () => {
  return addedGames.value
}

defineExpose({
  getGames,
})
</script>

<template>
  <div>
    <div>
      <DropDownSearch
        name="liked-games"
        :options="props.options"
        placeholder="Search for a game..."
        :disabled="false"
        :maxItems="5"
        @selected="(option) => (selectedGame = option)"
        @filter="(filter) => console.log('FILTER:', filter)"
      /><button @click="addGame">+</button>
    </div>
    <div class="addedgames">
      <div v-for="game in addedGames" :key="game.id">
        <div>{{ game.name }}</div>
        <button @click="removeGame(game)">x</button>
      </div>
    </div>
  </div>
</template>
