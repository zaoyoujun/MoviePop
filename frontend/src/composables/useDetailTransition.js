import { ref } from 'vue'

const transitionState = ref({
  isActive: false,
  imageSrc: '',
  startRect: null,
  movieId: null,
  phase: 'start'
})

export function useDetailTransition() {
  function startTransition(imageSrc, startRect, movieId) {
    transitionState.value = {
      isActive: true,
      imageSrc,
      startRect: { ...startRect },
      movieId,
      phase: 'start'
    }
  }

  function setPhase(phase) {
    transitionState.value.phase = phase
  }

  function completeTransition() {
    transitionState.value.isActive = false
    transitionState.value.imageSrc = ''
    transitionState.value.startRect = null
    transitionState.value.movieId = null
    transitionState.value.phase = 'start'
  }

  return {
    transitionState,
    startTransition,
    setPhase,
    completeTransition
  }
}
