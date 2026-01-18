function popquiz() {
    return {
        // State
        screen: 'input',
        category: '',
        count: 20,
        language: 'en',
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
        showAboutModal: false,
        showSubcategoriesModal: false,
        selectedImageIndex: 0,

        // Broad categories
        broadCategories: [],
        selectedBroadCategory: '',
        subcategories: [],
        loadingSubcategories: false,

        // Initialize - check URL params for shared quiz
        init() {
            const params = new URLSearchParams(window.location.search);
            const sharedCategory = params.get('category');
            const sharedCount = params.get('count');
            const sharedLang = params.get('lang');

            // Load broad categories
            this.loadBroadCategories();

            if (sharedCategory) {
                this.category = sharedCategory;
                if (sharedCount) this.count = Math.min(Math.max(parseInt(sharedCount) || 20, 5), 50);
                if (sharedLang) this.language = sharedLang;
                // Auto-generate the quiz
                this.generateList();
            }
        },

        // Update URL with current quiz params
        updateUrl() {
            const params = new URLSearchParams();
            params.set('category', this.category);
            params.set('count', this.count);
            if (this.language !== 'en') params.set('lang', this.language);
            const newUrl = `${window.location.pathname}?${params.toString()}`;
            history.replaceState({}, '', newUrl);
        },

        // Clear URL params
        clearUrl() {
            history.replaceState({}, '', window.location.pathname);
        },

        // Methods
        async loadSuggestions() {
            if (this.suggestions.length > 0) return; // Already loaded

            this.loadingSuggestions = true;
            try {
                const response = await fetch('/api/suggestions');
                const data = await response.json();
                if (response.status === 429) {
                    console.warn('Rate limited on suggestions');
                    return;
                }
                this.suggestions = data.suggestions || [];
            } catch (err) {
                console.error('Failed to load suggestions:', err);
            } finally {
                this.loadingSuggestions = false;
            }
        },

        async loadBroadCategories() {
            try {
                const response = await fetch('/api/broad-categories');
                const data = await response.json();
                this.broadCategories = data.categories || [];
            } catch (err) {
                console.error('Failed to load broad categories:', err);
            }
        },

        async openSubcategoriesModal(broadCategory) {
            this.selectedBroadCategory = broadCategory;
            this.subcategories = [];
            this.showSubcategoriesModal = true;
            this.loadingSubcategories = true;

            try {
                const response = await fetch('/api/subcategories', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ category: broadCategory })
                });

                const data = await response.json();

                if (response.status === 429) {
                    this.subcategories = [];
                    return;
                }

                this.subcategories = data.suggestions || [];
            } catch (err) {
                console.error('Failed to load subcategories:', err);
            } finally {
                this.loadingSubcategories = false;
            }
        },

        selectSubcategory(subcategory) {
            this.category = subcategory;
            this.showSubcategoriesModal = false;
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
                        count: parseInt(this.count),
                        language: this.language
                    })
                });

                const data = await response.json();

                if (response.status === 429) {
                    throw new Error(data.message || "You're going too fast! Please wait a moment before trying again.");
                }

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to generate list');
                }

                this.items = data.items || [];
                this.properties = data.properties || [];
                this.categoryDisplay = this.category;
                this.screen = 'study';

                // Update URL for sharing
                this.updateUrl();

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
                        properties: this.properties,
                        language: this.language
                    })
                });

                const data = await response.json();

                if (response.status === 429) {
                    this.error = data.message || "You're going too fast! Please wait a moment before trying again.";
                    return;
                }

                if (!response.ok) {
                    throw new Error(data.error || 'Failed to load item details');
                }

                this.currentItem = data;
                this.error = null;

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
            this.clearUrl();
        }
    };
}
