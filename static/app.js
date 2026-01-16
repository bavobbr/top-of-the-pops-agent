function popquiz() {
    return {
        // State
        screen: 'input',
        category: '',
        count: 20,
        loading: false,
        loadingItem: false,
        loadingSuggestions: false,
        error: null,

        // Data
        items: [],
        properties: [],
        categoryDisplay: '',
        currentItem: null,
        currentItemIndex: 0,
        suggestions: [],

        // UI
        showListModal: false,
        selectedImageIndex: 0,

        // Methods
        async loadSuggestions() {
            if (this.suggestions.length > 0) return; // Already loaded

            this.loadingSuggestions = true;
            try {
                const response = await fetch('/api/suggestions');
                const data = await response.json();
                this.suggestions = data.suggestions || [];
            } catch (err) {
                console.error('Failed to load suggestions:', err);
            } finally {
                this.loadingSuggestions = false;
            }
        },

        async generateList() {
            this.loading = true;
            this.error = null;

            try {
                const response = await fetch('/api/generate-list', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        category: this.category,
                        count: parseInt(this.count)
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to generate list');
                }

                this.items = data.items || [];
                this.properties = data.properties || [];
                this.categoryDisplay = this.category;
                this.screen = 'study';

                // Start at item #1
                await this.loadItem(0);

            } catch (err) {
                this.error = err.message;
            } finally {
                this.loading = false;
            }
        },

        async loadItem(index) {
            if (index < 0 || index >= this.items.length) return;

            this.loadingItem = true;
            this.currentItemIndex = index;
            this.selectedImageIndex = 0;

            try {
                const response = await fetch('/api/get-item-details', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        item: this.items[index],
                        category: this.categoryDisplay,
                        properties: this.properties
                    })
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to load item details');
                }

                this.currentItem = data;

            } catch (err) {
                this.currentItem = {
                    name: this.items[index],
                    description: 'Unable to load details: ' + err.message,
                    properties: {},
                    images: []
                };
            } finally {
                this.loadingItem = false;
            }
        },

        async loadNextItem() {
            // Go to next item, loop back to start if at end
            const nextIndex = (this.currentItemIndex + 1) % this.items.length;
            await this.loadItem(nextIndex);
        },

        async loadRandomItem() {
            if (this.items.length <= 1) {
                return;
            }
            // Pick a random index different from the current one
            let randomIndex;
            do {
                randomIndex = Math.floor(Math.random() * this.items.length);
            } while (randomIndex === this.currentItemIndex);
            await this.loadItem(randomIndex);
        },

        async selectItem(index) {
            this.showListModal = false;
            await this.loadItem(index);
        },

        startNewQuiz() {
            this.screen = 'input';
            this.items = [];
            this.properties = [];
            this.currentItem = null;
            this.currentItemIndex = 0;
            this.category = '';
            this.error = null;
        }
    };
}
