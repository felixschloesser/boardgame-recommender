<script lang="ts" setup>
import DropDownSearch from './DropDownSearch.vue'
import type { Option } from '../boardGame.mjs'
import { ref } from 'vue'
import * as api from '@/api.mjs'
import type BoardGame from '../boardGame.mjs'

interface Props {
  options: Option[]
  preAdded?: Option[] //preAdded games, can be empty
}

const props = defineProps<Props>()
const selectedGame = ref<Option | undefined>(undefined)
const options = ref<Option[]>(props.options)

const emit = defineEmits(['addGame', 'removeGame'])
const addedGames = ref<Option[]>(props.preAdded ?? [])

const addGame = () => {
  if (selectedGame.value) {
    // Avoid adding duplicates
    if (!addedGames.value.find((game) => game.id === selectedGame.value?.id)) {
      addedGames.value.push(selectedGame.value)
      emit('addGame', selectedGame.value)
    }
    selectedGame.value = undefined
  }
}

const removeGame = (game: Option) => {
  addedGames.value = addedGames.value.filter((g) => g.id !== game.id)
  emit('removeGame', game)
}

const refetchOptions = async (filter: string) => {
  options.value.splice(0, options.value.length) // Clear current options
  const newGames: BoardGame[] = await api.getGames(filter)
  const newOptions = newGames.map((game) => ({
    id: game.id,
    name: game.title,
  }))
  options.value.push(...newOptions)
}
</script>

<template>
  <div>
    <div class="inputgames">
      <DropDownSearch
        name="liked-games"
        :options="options"
        placeholder="Search for a game..."
        :disabled="false"
        :maxItems="5"
        @selected="(option) => (selectedGame = option)"
        @filter="(filter) => refetchOptions(filter)"
      /><button class="add-btn" @click="addGame">+</button>
    </div>
    <div class="addedgames">
      <div class="game" v-for="game in addedGames" :key="game.id">
        <div class="game-name">{{ game.name }}</div>
        <button class="remove-btn" @click="removeGame(game)">x</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.inputgames {
  display: flex;
  align-items: center;
  width: 250px;
  gap: 8px;
  justify-content: center; /* Center align horizontally */
  margin: 0 auto; /* Center align the container */
}

.add-btn {
  color: black;
  font-weight: bold;
  border-radius: 5px;
  border: none;
  cursor: pointer;
  font-size: 20px;
  width: 32px;
  height: 32px;
}

.addedgames {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.game {
  display: flex;
  align-self: left;
  margin-top: 8px;
  gap: 8px;
}

.game-name {
  font-family: 'Arial', sans-serif;
  font-weight: 400;
}

.remove-btn {
  color: black;
  font-weight: bold;
  border-radius: 5px;
  border: none;
  background-color: lightcoral;
  cursor: pointer;
  font-size: 16px;
}
</style>
