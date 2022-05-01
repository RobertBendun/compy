#include <cassert>
#include <cstdint>
#include <iostream>
#include <optional>
#include <string>
#include <unordered_map>
#include <variant>

namespace python
{
	struct None {} None;
	using Value_Variant = std::variant<struct None, bool, int, std::string>;

	struct Value : Value_Variant
	{
		Value() : Value_Variant{None} {}
		Value(struct None) : Value() {}
		Value(bool b) : Value_Variant{b} {}
		Value(std::string str) : Value_Variant{std::move(str)} {}

		bool is_none() const
		{
			return std::holds_alternative<struct None>(*this);
		}
	};

	struct Keyword_Arguments
	{
		std::unordered_map<std::string, Value> dict;

		inline Keyword_Arguments& append(std::string const& key, Value value)
		{
			dict[key] = std::move(value);
			return *this;
		}
	};

	struct Error
	{
		std::string_view type;
		std::string message{};

		Error operator()(std::string message)
		{
			return { type, std::move(message) };
		}

		void print(std::ostream& os) const
		{
			os << type << ": " << message << std::endl;
		}
	};

	Error type_error{"TypeError"};

	template<typename T>
	T assert_type(Value const& value, auto const& message)
	{
		if (std::holds_alternative<T>(value)) {
			return std::get<T>(value);
		}

		throw type_error(message);
	}

	template<typename T>
	T type_or_none_default(Value const& value, T def, auto const& message)
	{
		if (std::holds_alternative<T>(value)) {
			return std::get<T>(value);
		}
		if (std::holds_alternative<struct None>(value)) {
			return def;
		}

		throw type_error(message);
	}

	template<typename T>
	T type_or_none(Value const& value, auto const& message)
	{
		return type_or_none_default<T>(value, {}, message);
	}
}

std::string operator"" _str(char const* str, unsigned long length)
{
	return { str, length };
}

auto str(auto v)
{
	return std::to_string(v);
}

namespace python
{
	struct Printer
	{
		std::string separator = " ";
		std::string end = "\n";
		bool flush = false;

		void print(auto const& arg0, auto const& ...args)
		{
			std::cout << arg0;
			if constexpr (sizeof...(args) > 0) {
				((std::cout << separator) << ... << args);
			}
			print();
		}

		void print()
		{
			std::cout << end;
			if (flush) {
				std::cout << std::flush;
			}
		}
	};
}

void print(python::Keyword_Arguments kw, auto const& ...args)
{
	python::Printer printer;
	if (kw.dict.contains("sep") && not kw.dict["sep"].is_none()) {
		printer.separator = python::assert_type<std::string>(kw.dict["sep"], "sep must be None or a string");
	}

	if (kw.dict.contains("end") && not kw.dict["end"].is_none()) {
		printer.end = python::type_or_none<std::string>(kw.dict["end"], "end must be None or a string");
	}

	if (kw.dict.contains("flush") && not kw.dict["flush"].is_none()) {
		printer.flush = python::assert_type<bool>(kw.dict["flush"], "flush must be None or a bool");
	}

	assert(!kw.dict.contains("file") && "File specification for print() function is not implemented yet");
	printer.print(args...);
}

void print(auto const& ...args)
{
	python::Printer{}.print(args...);
}

void compy_main();

int main()
{
	try {
		compy_main();
	} catch (python::Error const& error) {
		error.print(std::cerr);
		return 1;
	}
}
