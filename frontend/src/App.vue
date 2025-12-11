<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { Participant } from './api.mts'
import * as api from './api.mts'

const participant = ref(null as Participant | null)

// todo fetch study group & session info from backend
onMounted(async () => {
  // check if participant ID exists in local storage
  const storedParticipantId = localStorage.getItem('participant_id')
  if (storedParticipantId) {
    participant.value = { participant_id: storedParticipantId }
    console.log('Existing participant ID:', storedParticipantId)
  } else {
    // create new participant
    participant.value = await api.newParticipant().then((participant) => {
      console.log('New participant ID:', participant.participant_id)
      return participant
    })
    // store participant ID in local storage
    if (participant.value) localStorage.setItem('participant_id', participant.value.participant_id)
  }
})
</script>

<template>
  <main>
    <RouterView v-slot="{ Component }">
      <component :is="Component" explanationStyle="analogy" />
    </RouterView>
  </main>
</template>

<!-- Global styles --->
<style>
body {
  font-family: Arial, sans-serif;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100vh;
}

.icon {
  width: 35px;
  height: 35px;
  padding: 10px;
  cursor: pointer;
}

.small-icon {
  width: 25x;
  height: 25px;
  display: block;
  cursor : pointer;
}

.navbar {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
</style>
