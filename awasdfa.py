import re

text = "Ronin/Видео/test/helloworld"
result = re.sub(r'\/[^\/]+$', '', text)

print(result)
