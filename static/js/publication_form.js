(function () {
    'use strict';

    var MAX_FILES = 10;

    function renderPreview(box, files) {
        box.innerHTML = '';
        files.forEach(function (file, index) {
            if (!file.type || file.type.indexOf('image/') !== 0) return;
            var wrap = document.createElement('div');
            wrap.className = 'pub-preview-item';
            wrap.title = file.name;
            var img = document.createElement('img');
            img.alt = file.name;
            var btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'pub-preview-remove';
            btn.setAttribute('data-index', String(index));
            btn.setAttribute('aria-label', 'Убрать фото');
            btn.textContent = '×';
            var reader = new FileReader();
            reader.onload = function (e) { img.src = e.target.result; };
            reader.readAsDataURL(file);
            wrap.appendChild(img);
            wrap.appendChild(btn);
            box.appendChild(wrap);
        });

        if (files.length >= MAX_FILES) {
            var warn = document.createElement('div');
            warn.className = 'pub-preview-warning';
            warn.textContent = 'Достигнут лимит: ' + MAX_FILES + ' фото';
            box.appendChild(warn);
        }
    }

    function bindInput(input) {
        var targetId = input.getAttribute('data-preview-target');
        if (!targetId) return;
        var box = document.getElementById(targetId);
        if (!box) return;
        var selectedFiles = [];

        function syncInput() {
            try {
                var dt = new DataTransfer();
                selectedFiles.forEach(function (f) { dt.items.add(f); });
                input.files = dt.files;
            } catch (e) {

            }
        }

        function isDuplicate(file) {
            return selectedFiles.some(function (x) {
                return x.name === file.name && x.size === file.size;
            });
        }

        input.addEventListener('change', function () {
            var picked = Array.prototype.slice.call(input.files || []);

            picked.forEach(function (file) {
                if (selectedFiles.length >= MAX_FILES) return;
                if (isDuplicate(file)) return;
                selectedFiles.push(file);
            });

            syncInput();
            renderPreview(box, selectedFiles);
        });

        box.addEventListener('click', function (e) {
            var btn = e.target.closest('.pub-preview-remove');
            if (!btn) return;

            var idx = parseInt(btn.getAttribute('data-index'), 10);
            if (isNaN(idx) || idx < 0 || idx >= selectedFiles.length) return;

            selectedFiles.splice(idx, 1);
            syncInput();
            renderPreview(box, selectedFiles);
        });
    }

    function init() {
        var inputs = document.querySelectorAll('.pub-images-input');
        Array.prototype.forEach.call(inputs, bindInput);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();