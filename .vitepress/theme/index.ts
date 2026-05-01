import DefaultTheme from 'vitepress/theme'
import TagCloud from './TagCloud.vue'

export default {
    extends: DefaultTheme,
    enhanceApp({ app }) {
        app.component('TagCloud', TagCloud)
    },
}
