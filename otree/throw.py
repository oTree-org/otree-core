   {% if entry.category == 'General Member' %}
        <a href="{% url 'member:person-list' %}"><li>{{ entry.category }}</li></a>
    {% elif entry.category == 'Executive Committee Member' %}
        <a href="{% url 'member:execomember-list' %}"><li>{{ entry.category}}</li></a>
    {% else %}
    <a href="{% url 'member:person-list' %}"><li>{{ entry.category}}</li></a>
        {% endif %}